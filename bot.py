import os
import time
import requests
import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction, ButtonStyle
from dotenv import load_dotenv

# Load env vars for Railway/development
load_dotenv()

# ENVIRONMENT VARIABLES
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LUARMOR_API_KEY = os.getenv("LUARMOR_API_KEY")
LUARMOR_PROJECT_ID = os.getenv("LUARMOR_PROJECT_ID")
BASE_URL = "https://api.luarmor.net/v3"

# CHANGE THIS TO YOUR ROLE ID
AUTHORIZED_ROLE = 1405035087703183492  # Only users with this role can interact

# Only allow this user to run /panel (replace with your real Discord user ID if you want)
PANEL_COMMAND_USER_ID = 0  # <--- CHANGE THIS TO YOUR DISCORD USER ID TO RESTRICT, or leave as 0 for all users

# Channel where you want the embed to be sent
PANEL_CHANNEL_ID = 1411369197627248830

HEADERS = {
    "Authorization": LUARMOR_API_KEY,
    "Content-Type": "application/json"
}

# Per-user rate limit tracking for HWID reset (2 hours)
hwid_reset_timers = {}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Utility: robust API call
def safe_api_call(func, *args, **kwargs):
    try:
        resp = func(*args, **kwargs)
        try:
            return resp.json()
        except Exception:
            return {"success": False, "message": f"Invalid response from Luarmor ({resp.status_code}): {resp.text}"}
    except Exception as e:
        return {"success": False, "message": f"API call error: {e}"}

class LuarmorView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Generate Key", style=ButtonStyle.green, custom_id="generate_key")
    async def generate_key(self, interaction: Interaction, button: ui.Button):
        if not await has_role(interaction.user, interaction.guild):
            return await interaction.response.send_message(
                "You are not authorized to use this!", ephemeral=True)
        data = safe_api_call(create_key)
        key = data.get("user_key")
        msg = f"**Generated Key:** `{key}`" if key else f"Failed to generate key: {data.get('message', 'Unknown error')}"
        # Send as a public message in the channel
        await interaction.response.send_message(msg, ephemeral=False)

    @ui.button(label="Get Key Info", style=ButtonStyle.blurple, custom_id="get_key")
    async def get_key(self, interaction: Interaction, button: ui.Button):
        if not await has_role(interaction.user, interaction.guild):
            return await interaction.response.send_message(
                "You are not authorized to use this!", ephemeral=True)
        modal = KeyModal("get")
        await interaction.response.send_modal(modal)

    @ui.button(label="Reset HWID", style=ButtonStyle.red, custom_id="reset_hwid")
    async def reset_hwid(self, interaction: Interaction, button: ui.Button):
        if not await has_role(interaction.user, interaction.guild):
            return await interaction.response.send_message(
                "You are not authorized to use this!", ephemeral=True)
        modal = KeyModal("reset")
        await interaction.response.send_modal(modal)

class KeyModal(ui.Modal, title="Key Required"):
    key = ui.TextInput(label="Enter Key", style=discord.TextStyle.short)

    def __init__(self, action):
        super().__init__()
        self.action = action

    async def on_submit(self, interaction: Interaction):
        user_id = interaction.user.id
        key_value = self.key.value.strip()
        if self.action == "get":
            data = safe_api_call(get_key_info, key_value)
            if data.get("success") and data.get('users'):
                user = data['users'][0]
                embed = discord.Embed(title="Key Info - eps1llon hub premium", color=discord.Color.blurple())
                embed.add_field(name="Key", value=user.get("user_key", "-"), inline=False)
                embed.add_field(name="Status", value=user.get("status", "-"), inline=True)
                embed.add_field(name="HWID", value=user.get("identifier", "-"), inline=True)
                embed.add_field(name="Discord ID", value=user.get("discord_id", "-"), inline=True)
                expires = user.get("auth_expire", -1)
                expires_fmt = "<never>" if expires == -1 else f"<t:{expires}:f>"
                embed.add_field(name="Expires At", value=expires_fmt, inline=True)
                embed.add_field(name="Total Resets", value=user.get("total_resets", "0"), inline=True)
                embed.add_field(name="Total Executions", value=user.get("total_executions", "0"), inline=True)
                banned = "Yes" if user.get("banned") else "No"
                embed.add_field(name="Banned", value=banned, inline=True)
                await interaction.response.send_message(embed=embed, ephemeral=False)
            else:
                await interaction.response.send_message(
                    f"Failed to fetch key: {data.get('message', 'Unknown error')}", ephemeral=False)
        elif self.action == "reset":
            now = time.time()
            last = hwid_reset_timers.get(user_id, 0)
            if now - last < 7200:
                left = int((7200 - (now - last)) / 60)
                return await interaction.response.send_message(
                    f"You can reset HWID again in {left} min.", ephemeral=False)
            resp = safe_api_call(reset_hwid, key_value)
            if resp.get("success"):
                hwid_reset_timers[user_id] = now
                await interaction.response.send_message("HWID reset successful!", ephemeral=False)
            else:
                await interaction.response.send_message(
                    f"Failed to reset HWID: {resp.get('message', 'Unknown error')}", ephemeral=False)

async def has_role(member, guild):
    if guild is None:
        return False
    role = discord.utils.get(guild.roles, id=AUTHORIZED_ROLE)
    if role is None:
        return False
    return role in getattr(member, "roles", [])

# Luarmor API helpers (just requests, error handled above)
def create_key():
    url = f"{BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users"
    return requests.post(url, headers=HEADERS, json={})

def get_key_info(user_key):
    url = f"{BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users?user_key={user_key}"
    return requests.get(url, headers=HEADERS)

def reset_hwid(user_key):
    url = f"{BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users/resethwid"
    return requests.post(url, headers=HEADERS, json={"user_key": user_key})

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="panel", description="Post the eps1llon hub premium Luarmor panel in the configured channel.")
async def panel(interaction: Interaction):
    # Only allow the panel command in that channel, or by the specified user, or both
    if interaction.channel.id != PANEL_CHANNEL_ID:
        await interaction.response.send_message(
            f"Please use this command in <#{PANEL_CHANNEL_ID}>.", ephemeral=True)
        return
    embed = discord.Embed(
        title="eps1llon hub premium - Luarmor Panel",
        description="Manage your license keys and HWID for **eps1llon hub premium**.\n\n"
                    "**Actions:**\n"
                    "• Generate Key\n"
                    "• Get Key Info\n"
                    "• Reset HWID (once every 2 hours)\n\n"
                    "Only users with the required role can interact.",
        color=discord.Color.dark_magenta()
    )
    embed.set_footer(text="eps1llon hub premium | Powered by Luarmor")
    # Send as a public message in the channel, not ephemeral
    channel = interaction.guild.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=LuarmorView())
        await interaction.response.send_message("Panel sent!", ephemeral=True)
    else:
        await interaction.response.send_message("Failed: Target channel not found.", ephemeral=True)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
