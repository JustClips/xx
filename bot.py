import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
import json
import sys
import traceback
import logging
from typing import Optional

# =========================================================
# Logging Setup
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
log = logging.getLogger("eps1llon-bot")

# =========================================================
# Try to import MySQL connector
# =========================================================
try:
    import mysql.connector
    from mysql.connector import Error, pooling
    MYSQL_CONNECTOR_AVAILABLE = True
except ImportError:
    MYSQL_CONNECTOR_AVAILABLE = False
    log.warning("mysql-connector-python NOT installed. Falling back to in-memory storage ONLY.")

# =========================================================
# Environment Variables
# =========================================================
load_dotenv()

DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
CHANNEL_ID      = os.getenv("CHANNEL_ID")
LUARMOR_API_KEY = os.getenv("LUARMOR_API_KEY")
PROJECT_ID      = os.getenv("PROJECT_ID")

# Railway MySQL variables (Railway may expose either MYSQL_DATABASE or MYSQLDATABASE)
DB_HOST = os.getenv("MYSQLHOST")
DB_USER = os.getenv("MYSQLUSER")
DB_PASSWORD = os.getenv("MYSQLPASSWORD")
DB_NAME = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE")
DB_PORT = os.getenv("MYSQLPORT", "3306")  # Railway usually provides MYSQLPORT

if not DISCORD_TOKEN or not CHANNEL_ID:
    raise SystemExit("Missing DISCORD_TOKEN or CHANNEL_ID environment variables.")

if not LUARMOR_API_KEY or not PROJECT_ID:
    raise SystemExit("Missing LUARMOR_API_KEY or PROJECT_ID environment variables.")

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    raise SystemExit("CHANNEL_ID must be an integer.")

# =========================================================
# MySQL / Storage Layer
# =========================================================

# In-memory fallback storage
user_keys_memory = {}
user_reset_counts = {}

class StorageManager:
    def __init__(self):
        self.using_mysql = (
            MYSQL_CONNECTOR_AVAILABLE and
            all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME])
        )
        self.pool: Optional[pooling.MySQLConnectionPool] = None

        if self.using_mysql:
            try:
                self.pool = pooling.MySQLConnectionPool(
                    pool_name="eps_pool",
                    pool_size=5,
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    port=int(DB_PORT),
                    autocommit=True,
                    connection_timeout=10,
                )
                log.info("MySQL connection pool created successfully.")
            except Error as e:
                log.error(f"Failed to create MySQL pool: {e}")
                self.using_mysql = False
        else:
            if not MYSQL_CONNECTOR_AVAILABLE:
                log.info("MySQL connector not installed or DB vars missing. Using in-memory store.")
            else:
                log.info("MySQL not fully configured (missing env vars). Using in-memory store.")

        # Create tables if MySQL is available
        if self.using_mysql:
            self.create_tables()

    def get_connection(self):
        if not self.using_mysql or not self.pool:
            return None
        try:
            return self.pool.get_connection()
        except Error as e:
            log.error(f"Error getting connection from pool: {e}")
            return None

    def create_tables(self):
        conn = self.get_connection()
        if not conn:
            log.warning("No MySQL connection; cannot create tables (falling back to memory).")
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_keys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    discord_id BIGINT UNIQUE NOT NULL,
                    user_key VARCHAR(64) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reset_count INT DEFAULT 0,
                    INDEX idx_discord_id (discord_id),
                    INDEX idx_user_key (user_key)
                )
            """)
            conn.commit()
            cur.close()
            log.info("Ensured table 'user_keys' exists.")
        except Error as e:
            log.error(f"Error creating tables: {e}")
            self.using_mysql = False  # fallback
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # -------------------------
    # CRUD methods
    # -------------------------
    def get_user_key(self, discord_id: int) -> str:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return user_keys_memory.get(discord_id, "")
            try:
                cur = conn.cursor()
                cur.execute("SELECT user_key FROM user_keys WHERE discord_id = %s", (discord_id,))
                row = cur.fetchone()
                cur.close()
                return row[0] if row else ""
            except Error as e:
                log.error(f"MySQL get_user_key error: {e}")
                return user_keys_memory.get(discord_id, "")
            finally:
                conn.close()
        else:
            return user_keys_memory.get(discord_id, "")

    def save_user_key(self, discord_id: int, user_key: str) -> bool:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                user_keys_memory[discord_id] = user_key
                return True
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO user_keys (discord_id, user_key)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE user_key = VALUES(user_key)
                """, (discord_id, user_key))
                conn.commit()
                cur.close()
                return True
            except Error as e:
                log.error(f"MySQL save_user_key error: {e}")
                user_keys_memory[discord_id] = user_key  # fallback store
                return True
            finally:
                conn.close()
        else:
            user_keys_memory[discord_id] = user_key
            return True

    def increment_reset_count(self, discord_id: int) -> bool:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                user_reset_counts[discord_id] = user_reset_counts.get(discord_id, 0) + 1
                return True
            try:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE user_keys
                    SET reset_count = reset_count + 1,
                        last_reset = CURRENT_TIMESTAMP
                    WHERE discord_id = %s
                """, (discord_id,))
                conn.commit()
                cur.close()
                return True
            except Error as e:
                log.error(f"MySQL increment_reset_count error: {e}")
                user_reset_counts[discord_id] = user_reset_counts.get(discord_id, 0) + 1
                return True
            finally:
                conn.close()
        else:
            user_reset_counts[discord_id] = user_reset_counts.get(discord_id, 0) + 1
            return True

    def get_reset_count(self, discord_id: int) -> int:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return user_reset_counts.get(discord_id, 0)
            try:
                cur = conn.cursor()
                cur.execute("SELECT reset_count FROM user_keys WHERE discord_id = %s", (discord_id,))
                row = cur.fetchone()
                cur.close()
                return row[0] if row else 0
            except Error as e:
                log.error(f"MySQL get_reset_count error: {e}")
                return user_reset_counts.get(discord_id, 0)
            finally:
                conn.close()
        else:
            return user_reset_counts.get(discord_id, 0)

    def stats(self) -> dict:
        """Return simple diagnostics for /dbstatus."""
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return {"using_mysql": True, "reachable": False, "rows": None}
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM user_keys")
                count = cur.fetchone()[0]
                cur.close()
                return {"using_mysql": True, "reachable": True, "rows": count}
            except Error as e:
                log.error(f"MySQL stats error: {e}")
                return {"using_mysql": True, "reachable": False, "rows": None}
            finally:
                conn.close()
        else:
            return {
                "using_mysql": False,
                "reachable": True,
                "rows": len(user_keys_memory)
            }

# Initialize storage manager
storage = StorageManager()

# =========================================================
# Bot Setup
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True  # Needs enabling in Discord Developer Portal
intents.members = True          # Privileged intent (enable in Developer Portal)
intents.presences = True        # Optional privileged intent

bot = commands.Bot(command_prefix="!", intents=intents)

# Role that can use the premium panel
AUTHORIZED_ROLE_ID = 1405035087703183492  # Replace with your real role ID

# =========================================================
# Luarmor API Functions
# =========================================================

async def create_user_key(discord_id: str) -> str:
    """Create a new user key via Luarmor API."""
    url = f"https://api.luarmor.net/v3/projects/{PROJECT_ID}/users"
    headers = {
        "Authorization": LUARMOR_API_KEY,
        "Content-Type": "application/json"
    }
    data = {"discord_id": discord_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("user_key", "")
            else:
                body = await response.text()
                log.error(f"Luarmor create_user_key API Error: {response.status} - {body}")
                return ""

async def reset_user_hwid(user_key: str) -> bool:
    """Reset user HWID via Luarmor API."""
    url = f"https://api.luarmor.net/v3/projects/{PROJECT_ID}/users/resethwid"
    headers = {
        "Authorization": LUARMOR_API_KEY,
        "Content-Type": "application/json"
    }
    data = {"user_key": user_key}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status != 200:
                body = await response.text()
                log.error(f"Luarmor reset HWID error: {response.status} - {body}")
            return response.status == 200

# =========================================================
# Events
# =========================================================

@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"Watching channel {CHANNEL_ID}.")
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} command(s).")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

# =========================================================
# UI View
# =========================================================

class PremiumPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # --- Generate Key ---
    @discord.ui.button(label="Generate Key", style=discord.ButtonStyle.success, custom_id="generate_key")
    async def generate_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role_ids = [role.id for role in getattr(interaction.user, 'roles', [])]
            if AUTHORIZED_ROLE_ID not in role_ids:
                await interaction.response.send_message("❌ You do not have permission to use this panel.", ephemeral=True)
                return

            existing_key = storage.get_user_key(interaction.user.id)
            if existing_key:
                await interaction.response.send_message(
                    "⚠️ You already have a generated key. Use the 'Get Script' button to retrieve it.",
                    ephemeral=True
                )
                return

            user_key = await create_user_key(str(interaction.user.id))
            if not user_key:
                await interaction.response.send_message("❌ Failed to generate key. Please try again later.", ephemeral=True)
                return

            storage.save_user_key(interaction.user.id, user_key)

            await interaction.response.send_message(
                "✅ Key generated successfully! Use the 'Get Script' button to retrieve your script.",
                ephemeral=True
            )
        except Exception as e:
            log.error(f"Error in generate_key handler: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

    # --- Get Script ---
    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary, custom_id="get_script")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role_ids = [role.id for role in getattr(interaction.user, 'roles', [])]
            if AUTHORIZED_ROLE_ID not in role_ids:
                await interaction.response.send_message("❌ You do not have permission to use this panel.", ephemeral=True)
                return

            user_key = storage.get_user_key(interaction.user.id)
            if not user_key:
                await interaction.response.send_message(
                    "❌ You don't have a generated key yet. Use the 'Generate Key' button first.",
                    ephemeral=True
                )
                return

            script = (
                f'script_key="{user_key}";\n'
                f'loadstring(game:HttpGet("https://api.luarmor.net/files/v3/loaders/'
                f'f40a8b8e2d4ea7ce9d8b28eff8c2676d.lua"))()'
            )

            await interaction.response.send_message(f"```lua\n{script}\n```", ephemeral=True)
        except Exception as e:
            log.error(f"Error in get_script handler: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

    # --- Reset HWID ---
    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.danger, custom_id="reset_hwid")
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role_ids = [role.id for role in getattr(interaction.user, 'roles', [])]
            if AUTHORIZED_ROLE_ID not in role_ids:
                await interaction.response.send_message("❌ You do not have permission to use this panel.", ephemeral=True)
                return

            user_key = storage.get_user_key(interaction.user.id)
            if not user_key:
                await interaction.response.send_message(
                    "❌ You don't have a generated key yet. Use the 'Generate Key' button first.",
                    ephemeral=True
                )
                return

            success = await reset_user_hwid(user_key)
            if success:
                storage.increment_reset_count(interaction.user.id)
                await interaction.response.send_message(
                    "✅ HWID reset successfully!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to reset HWID. Please try again later.",
                    ephemeral=True
                )
        except Exception as e:
            log.error(f"Error in reset_hwid handler: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

# =========================================================
# Slash Commands
# =========================================================

@bot.tree.command(name="sendpanel", description="Send the premium panel to the current channel.")
async def send_panel(interaction: discord.Interaction):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only server administrators can use this command.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Eps1llon Hub Premium Panel",
        description="Welcome to the Eps1llon Hub Premium Panel!\n\nUse the buttons below to manage your premium access.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="Instructions",
        value=(
            "1. Click **Generate Key** to create your premium key\n"
            "2. Click **Get Script** to retrieve your loader script\n"
            "3. Click **Reset HWID** if you need to reset your hardware ID"
        ),
        inline=False
    )
    embed.set_footer(text="Eps1llon Hub Premium")

    view = PremiumPanelView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Premium panel sent!", ephemeral=True)

@bot.tree.command(name="dbstatus", description="Show database status (admin only).")
async def dbstatus(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    stats = storage.stats()
    msg = (
        f"Using MySQL: {stats['using_mysql']}\n"
        f"Reachable: {stats['reachable']}\n"
        f"User rows: {stats['rows']}"
    )
    await interaction.response.send_message(f"```{msg}```", ephemeral=True)

# =========================================================
# Main Entrypoint
# =========================================================

def main():
    log.info("Starting bot...")
    log.info(
        "DB Config Summary: host=%s db=%s port=%s using_mysql=%s",
        DB_HOST, DB_NAME, DB_PORT, storage.using_mysql
    )
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        log.error(f"Fatal bot error: {e}\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()
