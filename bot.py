import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
import json
import mysql.connector
from mysql.connector import Error
import asyncio

# =========================================================
# Environment Variables
# =========================================================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
LUARMOR_API_KEY = os.getenv("LUARMOR_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")
DB_HOST = os.getenv("MYSQLHOST")
DB_USER = os.getenv("MYSQLUSER")
DB_PASSWORD = os.getenv("MYSQLPASSWORD")
DB_NAME = os.getenv("MYSQL_DATABASE")

if not DISCORD_TOKEN or not CHANNEL_ID:
    raise SystemExit("Missing DISCORD_TOKEN or CHANNEL_ID environment variables.")

if not LUARMOR_API_KEY or not PROJECT_ID:
    raise SystemExit("Missing LUARMOR_API_KEY or PROJECT_ID environment variables.")

if not DB_HOST or not DB_USER or not DB_PASSWORD or not DB_NAME:
    raise SystemExit("Missing database environment variables.")

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    raise SystemExit("CHANNEL_ID must be an integer.")

# =========================================================
# Database Setup
# =========================================================
def create_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def create_tables():
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                discord_id BIGINT UNIQUE NOT NULL,
                user_key VARCHAR(32) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reset_count INT DEFAULT 0,
                INDEX idx_discord_id (discord_id),
                INDEX idx_user_key (user_key)
            )
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"Error creating tables: {e}")
        return False

# Create tables on startup
if not create_tables():
    raise SystemExit("Failed to create database tables.")

# =========================================================
# Bot Setup
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Role that can generate keys
AUTHORIZED_ROLE_ID = 1405035087703183492

# =========================================================
# Database Functions
# =========================================================

def get_user_key(discord_id: int) -> str:
    """Get user key from database"""
    connection = create_connection()
    if not connection:
        return ""
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT user_key FROM user_keys WHERE discord_id = %s", (discord_id,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        return result[0] if result else ""
    except Error as e:
        print(f"Error getting user key: {e}")
        return ""

def save_user_key(discord_id: int, user_key: str) -> bool:
    """Save user key to database"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO user_keys (discord_id, user_key) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE user_key = %s
        """, (discord_id, user_key, user_key))
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"Error saving user key: {e}")
        return False

def delete_user_key(discord_id: int) -> bool:
    """Delete user key from database"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM user_keys WHERE discord_id = %s", (discord_id,))
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"Error deleting user key: {e}")
        return False

def increment_reset_count(discord_id: int) -> bool:
    """Increment reset count for user"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE user_keys 
            SET reset_count = reset_count + 1, last_reset = CURRENT_TIMESTAMP 
            WHERE discord_id = %s
        """, (discord_id,))
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"Error incrementing reset count: {e}")
        return False

# =========================================================
# Luarmor API Functions
# =========================================================

async def create_user_key(discord_id: str) -> str:
    """Create a new user key via Luarmor API"""
    url = f"https://api.luarmor.net/v3/projects/{PROJECT_ID}/users"
    headers = {
        "Authorization": LUARMOR_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "discord_id": discord_id
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("user_key", "")
            else:
                print(f"API Error: {response.status} - {await response.text()}")
                return ""

async def reset_user_hwid(user_key: str) -> bool:
    """Reset user HWID via Luarmor API"""
    url = f"https://api.luarmor.net/v3/projects/{PROJECT_ID}/users/resethwid"
    headers = {
        "Authorization": LUARMOR_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "user_key": user_key
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            return response.status == 200

# =========================================================
# Bot Events
# =========================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Watching channel {CHANNEL_ID}.")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# =========================================================
# Views and Components
# =========================================================

class PremiumPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Generate Key", style=discord.ButtonStyle.success, custom_id="generate_key")
    async def generate_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has authorized role
        role_ids = [role.id for role in getattr(interaction.user, 'roles', [])]
        if AUTHORIZED_ROLE_ID not in role_ids:
            await interaction.response.send_message(
                "❌ You do not have permission to use this panel.", ephemeral=True
            )
            return

        # Check if user already has a key
        existing_key = get_user_key(interaction.user.id)
        if existing_key:
            await interaction.response.send_message(
                "⚠️ You already have a generated key. Use the 'Get Script' button to retrieve it.", 
                ephemeral=True
            )
            return

        # Generate new key via Luarmor API
        user_key = await create_user_key(str(interaction.user.id))
        if not user_key:
            await interaction.response.send_message(
                "❌ Failed to generate key. Please try again later.", 
                ephemeral=True
            )
            return

        # Save key to database
        if not save_user_key(interaction.user.id, user_key):
            await interaction.response.send_message(
                "❌ Failed to save key. Please try again later.", 
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            f"✅ Key generated successfully! Use the 'Get Script' button to retrieve your script.",
            ephemeral=True
        )

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary, custom_id="get_script")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has authorized role
        role_ids = [role.id for role in getattr(interaction.user, 'roles', [])]
        if AUTHORIZED_ROLE_ID not in role_ids:
            await interaction.response.send_message(
                "❌ You do not have permission to use this panel.", ephemeral=True
            )
            return

        # Check if user has a key
        user_key = get_user_key(interaction.user.id)
        if not user_key:
            await interaction.response.send_message(
                "❌ You don't have a generated key yet. Use the 'Generate Key' button first.", 
                ephemeral=True
            )
            return

        script = f'script_key="{user_key}";\nloadstring(game:HttpGet("https://api.luarmor.net/files/v3/loaders/f40a8b8e2d4ea7ce9d8b28eff8c2676d.lua"))()'
        
        await interaction.response.send_message(
            f"```lua\n{script}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.danger, custom_id="reset_hwid")
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has authorized role
        role_ids = [role.id for role in getattr(interaction.user, 'roles', [])]
        if AUTHORIZED_ROLE_ID not in role_ids:
            await interaction.response.send_message(
                "❌ You do not have permission to use this panel.", ephemeral=True
            )
            return

        # Check if user has a key
        user_key = get_user_key(interaction.user.id)
        if not user_key:
            await interaction.response.send_message(
                "❌ You don't have a generated key yet. Use the 'Generate Key' button first.", 
                ephemeral=True
            )
            return

        success = await reset_user_hwid(user_key)
        
        if success:
            # Increment reset count in database
            increment_reset_count(interaction.user.id)
            await interaction.response.send_message(
                "✅ HWID reset successfully!", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to reset HWID. Please try again later.", 
                ephemeral=True
            )

# =========================================================
# Slash Commands
# =========================================================

@bot.tree.command(name="sendpanel", description="Send the premium panel to the channel")
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
    embed.add_field(name="Instructions", value=
        "1. Click **Generate Key** to create your premium key\n"
        "2. Click **Get Script** to retrieve your loader script\n"
        "3. Click **Reset HWID** if you need to reset your hardware ID", 
        inline=False
    )
    embed.set_footer(text="Eps1llon Hub Premium")

    view = PremiumPanelView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Premium panel sent!", ephemeral=True)

@bot.tree.command(name="adminstats", description="View premium panel statistics")
async def admin_stats(interaction: discord.Interaction):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only server administrators can use this command.", 
            ephemeral=True
        )
        return

    connection = create_connection()
    if not connection:
        await interaction.response.send_message("❌ Database connection failed.", ephemeral=True)
        return

    try:
        cursor = connection.cursor()
        
        # Get total users
        cursor.execute("SELECT COUNT(*) FROM user_keys")
        total_users = cursor.fetchone()[0]
        
        # Get recent users (last 24 hours)
        cursor.execute("SELECT COUNT(*) FROM user_keys WHERE created_at > DATE_SUB(NOW(), INTERVAL 1 DAY)")
        recent_users = cursor.fetchone()[0]
        
        # Get reset stats
        cursor.execute("SELECT SUM(reset_count) FROM user_keys")
        total_resets = cursor.fetchone()[0] or 0
        
        cursor.close()
        connection.close()

        embed = discord.Embed(
            title="📊 Premium Panel Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Users", value=f"{total_users}", inline=True)
        embed.add_field(name="New Users (24h)", value=f"{recent_users}", inline=True)
        embed.add_field(name="Total HWID Resets", value=f"{total_resets}", inline=True)
        embed.set_footer(text="Eps1llon Hub Admin")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Error as e:
        await interaction.response.send_message(f"❌ Database error: {e}", ephemeral=True)

# =========================================================
# Main
# =========================================================

def main():
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
