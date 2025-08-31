import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
import json

# =========================================================
# Environment Variables
# =========================================================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
LUARMOR_API_KEY = os.getenv("LUARMOR_API_KEY")
PROJECT_ID = os.getenv("PROJECT_ID")

if not DISCORD_TOKEN or not CHANNEL_ID:
    raise SystemExit("Missing DISCORD_TOKEN or CHANNEL_ID environment variables.")

if not LUARMOR_API_KEY or not PROJECT_ID:
    raise SystemExit("Missing LUARMOR_API_KEY or PROJECT_ID environment variables.")

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    raise SystemExit("CHANNEL_ID must be an integer.")

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

# In-memory storage for user keys (use a DB in production)
user_keys = {}

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
        if interaction.user.id in user_keys:
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

        # Store key in memory
        user_keys[interaction.user.id] = user_key
        
        # Disable button for this user
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send(
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
        if interaction.user.id not in user_keys:
            await interaction.response.send_message(
                "❌ You don't have a generated key yet. Use the 'Generate Key' button first.", 
                ephemeral=True
            )
            return

        user_key = user_keys[interaction.user.id]
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
        if interaction.user.id not in user_keys:
            await interaction.response.send_message(
                "❌ You don't have a generated key yet. Use the 'Generate Key' button first.", 
                ephemeral=True
            )
            return

        user_key = user_keys[interaction.user.id]
        success = await reset_user_hwid(user_key)
        
        if success:
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
