import os
import time
import requests
import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction, ButtonStyle
from dotenv import load_dotenv

load_dotenv()

# ENV VARS
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LUARMOR_API_KEY = os.getenv("LUARMOR_API_KEY")
LUARMOR_PROJECT_ID = os.getenv("LUARMOR_PROJECT_ID")
BASE_URL = "https://api.luarmor.net/v3"

AUTHORIZED_ROLE = 1405035087703183492  # Only users with this role can interact

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

class LuarmorView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Generate Key", style=ButtonStyle.green, custom_id="generate_key")
    async def generate_key(self, interaction: Interaction, button: ui.Button):
        if not await has_role(interaction.user, interaction.guild):
            return await interaction.response.send_message(
                "You are not authorized to use this!", ephemeral=True)
        # Generate key (minimal, you can expand options)
        data = create_key()
        key = data.get("user_key", "Failed to generate key.")
        await interaction.response.send_message(
            f"**Generated Key:** `{key}`", ephemeral=True)

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

# Modal for key input
class KeyModal(ui.Modal, title="Key Required"):
    key = ui.TextInput(label="Enter Key", style=discord.TextStyle.short)

    def __init__(self, action):
        super().__init__()
        self.action = action

    async def on_submit(self, interaction: Interaction):
        user_id = interaction.user.id
        key_value = self.key.value.strip()
        if self.action == "get":
            data = get_key_info(key_value)
            if data.get("success"):
                user = data['users'][0]
                embed = discord.Embed(title="Key Info", color=discord.Color.blurple())
                embed.add_field(name="Key", value=user.get("user_key", "-"))
                embed.add_field(name="Status", value=user.get("status", "-"))
                embed.add_field(name="HWID", value=user.get("identifier", "-"))
                embed.add_field(name="Discord ID", value=user.get("discord_id", "-"))
                embed.add_field(name="Expires At", value=user.get("auth_expire", "-"))
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"Failed to fetch key: {data.get('message', 'Unknown error')}", ephemeral=True)
        elif self.action == "reset":
            now = time.time()
            last = hwid_reset_timers.get(user_id, 0)
            if now - last < 7200:
                left = int((7200 - (now - last)) / 60)
                return await interaction.response.send_message(
                    f"You can reset HWID again in {left} min.", ephemeral=True)
            resp = reset_hwid(key_value)
            if resp.get("success"):
                hwid_reset_timers[user_id] = now
                await interaction.response.send_message("HWID reset successful!", ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"Failed to reset HWID: {resp.get('message', 'Unknown error')}", ephemeral=True)

async def has_role(member, guild):
    if guild is None:
        return False
    role = discord.utils.get(guild.roles, id=AUTHORIZED_ROLE)
    if role is None:
        return False
    return role in getattr(member, "roles", [])

# Luarmor API helpers
def create_key():
    url = f"{BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users"
    r = requests.post(url, headers=HEADERS, json={})
    return r.json()

def get_key_info(user_key):
    url = f"{BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users?user_key={user_key}"
    r = requests.get(url, headers=HEADERS)
    return r.json()

def reset_hwid(user_key):
    url = f"{BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users/resethwid"
    r = requests.post(url, headers=HEADERS, json={"user_key": user_key})
    return r.json()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="panel", description="Show the Luarmor control panel")
async def panel(interaction: Interaction):
    if not await has_role(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            "You are not authorized to use this!", ephemeral=True)
    embed = discord.Embed(
        title="Luarmor Panel",
        description="Use the buttons below to manage keys and HWID.",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="Luarmor Management Panel")
    await interaction.response.send_message(embed=embed, view=LuarmorView(), ephemeral=True)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
