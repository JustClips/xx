import os
import sys
import traceback
import logging
from typing import Optional, List, Tuple
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
log = logging.getLogger("eps1llon-bot")

# ---------------------------------------------------------
# MySQL Connector
# ---------------------------------------------------------
try:
    import mysql.connector
    from mysql.connector import Error, pooling
    MYSQL_CONNECTOR_AVAILABLE = True
except ImportError:
    MYSQL_CONNECTOR_AVAILABLE = False
    log.warning("mysql-connector-python not installed; using in-memory fallback (NOT persistent).")

# ---------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------
load_dotenv()

DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
CHANNEL_ID      = os.getenv("CHANNEL_ID")
LUARMOR_API_KEY = os.getenv("LUARMOR_API_KEY")
PROJECT_ID      = os.getenv("PROJECT_ID")

DB_HOST = os.getenv("MYSQLHOST")
DB_USER = os.getenv("MYSQLUSER")
DB_PASSWORD = os.getenv("MYSQLPASSWORD")
DB_NAME = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE")
DB_PORT = os.getenv("MYSQLPORT", "3306")

if not DISCORD_TOKEN or not CHANNEL_ID:
    raise SystemExit("Missing DISCORD_TOKEN or CHANNEL_ID.")
try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    raise SystemExit("CHANNEL_ID must be an integer.")

# Luarmor creds optional but required for HWID reset
if not LUARMOR_API_KEY or not PROJECT_ID:
    log.warning("Luarmor API credentials missing. HWID reset will fail.")

# ---------------------------------------------------------
# In-memory fallback structures (only if MySQL not available)
# ---------------------------------------------------------
memory_available_keys = []          # list of unassigned keys
memory_assigned = {}                # discord_id -> key
memory_key_to_user = {}             # key -> discord_id
memory_user_reset_counts = {}       # discord_id -> int

# ---------------------------------------------------------
# Storage Manager
# ---------------------------------------------------------
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
                    pool_name="main_pool",
                    pool_size=5,
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    port=int(DB_PORT),
                    autocommit=True,
                    connection_timeout=10
                )
                log.info("MySQL connection pool created.")
                self.create_tables()
            except Error as e:
                log.error(f"MySQL pool creation failed: {e}")
                self.using_mysql = False
        else:
            if not MYSQL_CONNECTOR_AVAILABLE:
                log.info("MySQL connector not installed; using memory mode.")
            else:
                log.info("MySQL environment variables incomplete; using memory mode.")

    # ------------- DB helpers -------------
    def get_connection(self):
        if not self.using_mysql or not self.pool:
            return None
        try:
            return self.pool.get_connection()
        except Error as e:
            log.error(f"Error getting connection: {e}")
            return None

    def create_tables(self):
        """
        available_keys: all keys; if assigned_to is NULL -> unused
        user_keys: record of assigned keys per discord_id (1:1), reset counters
        """
        conn = self.get_connection()
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS available_keys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    license_key VARCHAR(64) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_to BIGINT NULL,
                    assigned_tag VARCHAR(100) NULL,
                    assigned_at TIMESTAMP NULL,
                    INDEX idx_license_key (license_key),
                    INDEX idx_assigned_to (assigned_to)
                )
            """)
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
            log.info("Ensured tables available_keys & user_keys exist.")
        except Error as e:
            log.error(f"Table creation error: {e}")
        finally:
            conn.close()

    # ------------- Key allocation / queries -------------
    def user_has_key(self, discord_id: int) -> bool:
        return bool(self.get_user_key(discord_id))

    def get_user_key(self, discord_id: int) -> str:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return memory_assigned.get(discord_id, "")
            try:
                cur = conn.cursor()
                cur.execute("SELECT user_key FROM user_keys WHERE discord_id = %s", (discord_id,))
                row = cur.fetchone()
                cur.close()
                return row[0] if row else ""
            except Error as e:
                log.error(f"get_user_key error: {e}")
                return memory_assigned.get(discord_id, "")
            finally:
                conn.close()
        else:
            return memory_assigned.get(discord_id, "")

    def allocate_key(self, discord_id: int, tag: str) -> Optional[str]:
        """
        Assign first unassigned key (ordered by id). Returns key or None if none left.
        """
        existing = self.get_user_key(discord_id)
        if existing:
            return existing

        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return self._allocate_memory(discord_id)
            try:
                cur = conn.cursor()
                # fetch an unused key
                cur.execute("""
                    SELECT id, license_key FROM available_keys
                    WHERE assigned_to IS NULL
                    ORDER BY id ASC
                    LIMIT 1
                """)
                row = cur.fetchone()
                if not row:
                    cur.close()
                    return None
                key_id, license_key = row
                # mark assigned
                cur.execute("""
                    UPDATE available_keys
                    SET assigned_to = %s,
                        assigned_tag = %s,
                        assigned_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (discord_id, tag[:100], key_id))
                # insert record into user_keys
                cur.execute("""
                    INSERT INTO user_keys (discord_id, user_key)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE user_key = VALUES(user_key)
                """, (discord_id, license_key))
                conn.commit()
                cur.close()
                return license_key
            except Error as e:
                log.error(f"allocate_key error: {e}")
                return None
            finally:
                conn.close()
        else:
            return self._allocate_memory(discord_id)

    def _allocate_memory(self, discord_id: int) -> Optional[str]:
        if discord_id in memory_assigned:
            return memory_assigned[discord_id]
        if not memory_available_keys:
            return None
        key = memory_available_keys.pop(0)
        memory_assigned[discord_id] = key
        memory_key_to_user[key] = discord_id
        return key

    def import_keys(self, keys: List[str]) -> Tuple[int, int]:
        """
        Insert a list of raw key strings into available_keys (only new keys).
        Returns (inserted_count, skipped_count)
        """
        cleaned = []
        seen = set()
        for k in keys:
            k = k.strip()
            if not k:
                continue
            if k in seen:
                continue
            seen.add(k)
            cleaned.append(k)

        if self.using_mysql:
            if not cleaned:
                return (0, 0)
            conn = self.get_connection()
            if not conn:
                return (0, len(cleaned))
            inserted = 0
            skipped = 0
            try:
                cur = conn.cursor()
                for key in cleaned:
                    try:
                        cur.execute("INSERT IGNORE INTO available_keys (license_key) VALUES (%s)", (key,))
                        if cur.rowcount == 1:
                            inserted += 1
                        else:
                            skipped += 1
                    except Error:
                        skipped += 1
                conn.commit()
                cur.close()
            except Error as e:
                log.error(f"import_keys error: {e}")
                skipped += (len(cleaned) - inserted - skipped)
            finally:
                conn.close()
            return (inserted, skipped)
        else:
            inserted = 0
            skipped = 0
            for key in cleaned:
                if key in memory_available_keys or key in memory_key_to_user:
                    skipped += 1
                else:
                    memory_available_keys.append(key)
                    inserted += 1
            return (inserted, skipped)

    def list_keys(self, kind: str, page: int, page_size: int = 20) -> List[dict]:
        """
        kind: 'unused' or 'assigned'
        Returns list of dicts with license_key and metadata
        """
        offset = (page - 1) * page_size
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return []
            try:
                cur = conn.cursor(dictionary=True)
                if kind == "unused":
                    cur.execute("""
                        SELECT license_key, created_at
                        FROM available_keys
                        WHERE assigned_to IS NULL
                        ORDER BY id ASC
                        LIMIT %s OFFSET %s
                    """, (page_size, offset))
                else:
                    cur.execute("""
                        SELECT license_key, assigned_to, assigned_tag, assigned_at
                        FROM available_keys
                        WHERE assigned_to IS NOT NULL
                        ORDER BY assigned_at DESC
                        LIMIT %s OFFSET %s
                    """, (page_size, offset))
                rows = cur.fetchall()
                cur.close()
                return rows
            except Error as e:
                log.error(f"list_keys error: {e}")
                return []
            finally:
                conn.close()
        else:
            if kind == "unused":
                subset = memory_available_keys[offset:offset + page_size]
                return [{"license_key": k} for k in subset]
            else:
                # assigned
                items = [
                    {"license_key": key, "assigned_to": uid}
                    for uid, key in memory_assigned.items()
                ]
                items.sort(key=lambda x: x["license_key"])
                subset = items[offset:offset + page_size]
                return subset

    def key_info_by_user(self, discord_id: int) -> Optional[dict]:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return None
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("""
                    SELECT u.user_key, u.created_at, u.reset_count, u.last_reset
                    FROM user_keys u
                    WHERE u.discord_id = %s
                """, (discord_id,))
                row = cur.fetchone()
                if row:
                    # also fetch assigned_at from available_keys
                    cur.execute("""
                        SELECT assigned_at
                        FROM available_keys
                        WHERE license_key = %s
                    """, (row["user_key"],))
                    row2 = cur.fetchone()
                    if row2 and "assigned_at" in row2:
                        row["assigned_at"] = row2["assigned_at"]
                cur.close()
                return row
            except Error as e:
                log.error(f"key_info_by_user error: {e}")
                return None
            finally:
                conn.close()
        else:
            if discord_id not in memory_assigned:
                return None
            return {
                "user_key": memory_assigned[discord_id],
                "created_at": None,
                "reset_count": memory_user_reset_counts.get(discord_id, 0),
                "last_reset": None,
                "assigned_at": None
            }

    def key_info_by_key(self, key: str) -> Optional[dict]:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return None
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("""
                    SELECT license_key, assigned_to, assigned_tag, assigned_at, created_at
                    FROM available_keys
                    WHERE license_key = %s
                """, (key,))
                row = cur.fetchone()
                cur.close()
                return row
            except Error as e:
                log.error(f"key_info_by_key error: {e}")
                return None
            finally:
                conn.close()
        else:
            if key in memory_key_to_user:
                uid = memory_key_to_user[key]
                return {"license_key": key, "assigned_to": uid}
            if key in memory_available_keys:
                return {"license_key": key, "assigned_to": None}
            return None

    def increment_reset_count(self, discord_id: int):
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                memory_user_reset_counts[discord_id] = memory_user_reset_counts.get(discord_id, 0) + 1
                return
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
            except Error as e:
                log.error(f"increment_reset_count error: {e}")
            finally:
                conn.close()
        else:
            memory_user_reset_counts[discord_id] = memory_user_reset_counts.get(discord_id, 0) + 1

    def stats(self) -> dict:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return {"using_mysql": True, "reachable": False}
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM user_keys")
                assigned_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM available_keys WHERE assigned_to IS NULL")
                unused_count = cur.fetchone()[0]
                cur.close()
                return {
                    "using_mysql": True,
                    "reachable": True,
                    "assigned": assigned_count,
                    "unused": unused_count
                }
            except Error as e:
                log.error(f"stats error: {e}")
                return {"using_mysql": True, "reachable": False}
            finally:
                conn.close()
        else:
            return {
                "using_mysql": False,
                "reachable": True,
                "assigned": len(memory_assigned),
                "unused": len(memory_available_keys)
            }

storage = StorageManager()

# ---------------------------------------------------------
# Discord Bot Setup
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

AUTHORIZED_ROLE_ID = 1405035087703183492  # Replace with your authorized premium role ID

# ---------------------------------------------------------
# Luarmor: HWID reset (still uses user_key)
# ---------------------------------------------------------
async def reset_user_hwid(user_key: str) -> bool:
    if not (LUARMOR_API_KEY and PROJECT_ID):
        return False
    url = f"https://api.luarmor.net/v3/projects/{PROJECT_ID}/users/resethwid"
    headers = {
        "Authorization": LUARMOR_API_KEY,
        "Content-Type": "application/json"
    }
    data = {"user_key": user_key}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as resp:
            if resp.status != 200:
                log.error(f"Luarmor HWID reset failed {resp.status}: {await resp.text()}")
            return resp.status == 200

# ---------------------------------------------------------
# Utility
# ---------------------------------------------------------
def mask_key(k: str) -> str:
    if len(k) <= 10:
        return k
    return f"{k[:6]}...{k[-4:]}"

def user_is_admin(interaction: discord.Interaction) -> bool:
    return (
        interaction.user.guild_permissions.administrator or
        interaction.user.id == interaction.guild.owner_id
    )

def user_has_role(user: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in getattr(user, "roles", []))

# ---------------------------------------------------------
# Events
# ---------------------------------------------------------
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} command(s).")
    except Exception as e:
        log.error(f"Sync failed: {e}")

# ---------------------------------------------------------
# UI View (Panel Buttons)
# ---------------------------------------------------------
class PremiumPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Generate Key", style=discord.ButtonStyle.success, custom_id="generate_key")
    async def generate_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not user_has_role(interaction.user, AUTHORIZED_ROLE_ID):
                await interaction.response.send_message("❌ You lack the required role.", ephemeral=True)
                return

            key = storage.allocate_key(interaction.user.id, f"{interaction.user}")
            if not key:
                await interaction.response.send_message("❌ No unused keys remaining. Contact an admin.", ephemeral=True)
                return

            await interaction.response.send_message("✅ Key assigned! Use 'Get Script' to retrieve it.", ephemeral=True)
        except Exception as e:
            log.error(f"generate_key error: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary, custom_id="get_script")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not user_has_role(interaction.user, AUTHORIZED_ROLE_ID):
                await interaction.response.send_message("❌ You lack the required role.", ephemeral=True)
                return
            key = storage.get_user_key(interaction.user.id)
            if not key:
                await interaction.response.send_message("❌ You do not have a key yet. Press 'Generate Key'.", ephemeral=True)
                return
            script = (
                f'script_key="{key}";\n'
                f'loadstring(game:HttpGet("https://api.luarmor.net/files/v3/loaders/'
                f'f40a8b8e2d4ea7ce9d8b28eff8c2676d.lua"))()'
            )
            await interaction.response.send_message(f"```lua\n{script}\n```", ephemeral=True)
        except Exception as e:
            log.error(f"get_script error: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.danger, custom_id="reset_hwid")
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not user_has_role(interaction.user, AUTHORIZED_ROLE_ID):
                await interaction.response.send_message("❌ You lack the required role.", ephemeral=True)
                return
            key = storage.get_user_key(interaction.user.id)
            if not key:
                await interaction.response.send_message("❌ No key assigned.", ephemeral=True)
                return
            ok = await reset_user_hwid(key)
            if ok:
                storage.increment_reset_count(interaction.user.id)
                await interaction.response.send_message("✅ HWID reset successful.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ HWID reset failed.", ephemeral=True)
        except Exception as e:
            log.error(f"reset_hwid error: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

# ---------------------------------------------------------
# Slash Commands (Panel & Admin)
# ---------------------------------------------------------
@bot.tree.command(name="sendpanel", description="Send the premium panel (admins).")
async def sendpanel(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    embed = discord.Embed(
        title="Eps1llon Hub Premium Panel",
        description="Manage your premium access below.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="Instructions",
        value="1. Generate Key\n2. Get Script\n3. Reset HWID",
        inline=False
    )
    embed.set_footer(text="Eps1llon Hub Premium")
    view = PremiumPanelView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panel sent.", ephemeral=True)

@bot.tree.command(name="dbstatus", description="Show database/key stats (admin).")
async def dbstatus(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    stats = storage.stats()
    if not stats.get("reachable", True):
        msg = "DB unreachable."
    else:
        msg = (
            f"Using MySQL: {stats['using_mysql']}\n"
            f"Assigned keys: {stats.get('assigned')}\n"
            f"Unused keys: {stats.get('unused')}"
        )
    await interaction.response.send_message(f"```{msg}```", ephemeral=True)

# Import keys from a text file
@bot.tree.command(name="importkeys", description="Import unused keys from a .txt file (one per line).")
@app_commands.describe(file="Attach a .txt file containing one key per line.")
async def importkeys(interaction: discord.Interaction, file: discord.Attachment):
    if not user_is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    if not file.filename.lower().endswith(".txt"):
        await interaction.response.send_message("❌ Please attach a .txt file.", ephemeral=True)
        return
    content = await file.read()
    try:
        lines = content.decode("utf-8", errors="ignore").splitlines()
    except Exception:
        await interaction.response.send_message("❌ Failed to decode file.", ephemeral=True)
        return
    inserted, skipped = storage.import_keys(lines)
    await interaction.response.send_message(
        f"✅ Import complete. Inserted: {inserted}, Skipped (duplicates/invalid): {skipped}",
        ephemeral=True
    )

# List keys (unused or assigned)
@bot.tree.command(name="listkeys", description="List unused or assigned keys (admin).")
@app_commands.describe(
    kind="unused or assigned",
    page="Page number (starting at 1)",
    full="Show full keys instead of masked (admin caution)."
)
async def listkeys(interaction: discord.Interaction, kind: str, page: int = 1, full: bool = False):
    if not user_is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    kind = kind.lower()
    if kind not in ("unused", "assigned"):
        await interaction.response.send_message("❌ kind must be 'unused' or 'assigned'.", ephemeral=True)
        return
    if page < 1:
        page = 1
    rows = storage.list_keys(kind, page)
    if not rows:
        await interaction.response.send_message("No results for that page.", ephemeral=True)
        return

    lines = []
    for r in rows:
        key = r.get("license_key")
        display = key if full else mask_key(key)
        if kind == "unused":
            lines.append(f"{display}")
        else:
            assigned_to = r.get("assigned_to")
            tag = r.get("assigned_tag")
            assigned_at = r.get("assigned_at")
            lines.append(f"{display} -> {assigned_to} ({tag}) at {assigned_at}")
    output = "\n".join(lines)
    if full:
        output = f"(FULL KEYS - KEEP PRIVATE)\n{output}"
    await interaction.response.send_message(f"```{output}```", ephemeral=True)

# Key / user lookup
@bot.tree.command(name="keyinfo", description="Lookup key info by user or key (admin).")
@app_commands.describe(
    user="User to inspect (optional)",
    key="Exact key string (optional)"
)
async def keyinfo(interaction: discord.Interaction, user: Optional[discord.Member] = None, key: Optional[str] = None):
    if not user_is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    if (user is None and key is None) or (user is not None and key is not None):
        await interaction.response.send_message("Provide either user OR key (not both).", ephemeral=True)
        return

    if user:
        info = storage.key_info_by_user(user.id)
        if not info:
            await interaction.response.send_message("User has no key.", ephemeral=True)
            return
        msg = (
            f"User: {user} ({user.id})\n"
            f"Key: {info.get('user_key')}\n"
            f"Assigned/Created: {info.get('created_at')}\n"
            f"Reset Count: {info.get('reset_count')}\n"
            f"Last Reset: {info.get('last_reset')}"
        )
        await interaction.response.send_message(f"```{msg}```", ephemeral=True)
    else:
        info = storage.key_info_by_key(key)
        if not info:
            await interaction.response.send_message("Key not found.", ephemeral=True)
            return
        assigned_to = info.get("assigned_to")
        msg = (
            f"Key: {info.get('license_key')}\n"
            f"Assigned To: {assigned_to}\n"
            f"Assigned Tag: {info.get('assigned_tag')}\n"
            f"Assigned At: {info.get('assigned_at')}\n"
            f"Created At: {info.get('created_at')}"
        )
        await interaction.response.send_message(f"```{msg}```", ephemeral=True)

# ---------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------
def main():
    log.info(
        "Startup DB Summary host=%s db=%s port=%s using_mysql=%s",
        DB_HOST, DB_NAME, DB_PORT, storage.using_mysql
    )
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        log.error(f"Fatal error: {e}\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()
