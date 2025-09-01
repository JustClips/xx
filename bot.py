import discord
from discord.ext import commands
from discord import app_commands
import requests
import json
import os

# --- CONFIGURATION ---
# Updated to match Railway environment variables.
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")
LUARMOR_API_KEY = os.environ.get("LUARMOR_API_KEY", "YOUR_LUARMOR_API_KEY_HERE")
LUARMOR_PROJECT_ID = os.environ.get("PROJECT_ID", "YOUR_LUARMOR_PROJECT_ID_HERE")
# <<!>> IMPORTANT: Set the Role ID that is required to use the script panel buttons.
REQUIRED_ROLE_ID = 1405035087703183492 

LUARMOR_BASE_URL = "https://api.luarmor.net/v3"
# Corrected the loader URL to the static link you provided.
LUARMOR_LOADER_URL = "https://api.luarmor.net/files/v3/loaders/f40a8b8e2d4ea7ce9d8b28eff8c2676d.lua"


# --- PERSISTENT VIEW FOR SCRIPT PANEL ---
class ScriptPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Checks if the user has the required role before any button callback is run."""
        # Ensure the interaction is in a guild context
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This interaction can only be used in a server.", ephemeral=True)
            return False

        role = interaction.guild.get_role(REQUIRED_ROLE_ID)
        if role is None:
            # This is a server-side configuration error, let the user know.
            print(f"Error: Role with ID {REQUIRED_ROLE_ID} not found in guild {interaction.guild.name}")
            await interaction.response.send_message("Configuration error: The required role could not be found on this server.", ephemeral=True)
            return False
            
        if role not in interaction.user.roles:
            await interaction.response.send_message(f"You need the **{role.name}** role to use this button.", ephemeral=True)
            return False
            
        return True

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.success, custom_id="persistent_view:get_script")
    async def get_script_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        discord_id = str(interaction.user.id)
        user_data = await get_user_by_discord_id(discord_id)
        
        # If user already has a key, just give them the script string
        if user_data and user_data.get("user_key"):
            key = user_data["user_key"]
            script_string = f'script_key="{key}";loadstring(game:HttpGet("{LUARMOR_LOADER_URL}"))()'
            await interaction.followup.send(f"You already have a key. Here is your script:\n```{script_string}```", ephemeral=True)
            return

        # If no key, generate a new one
        url = f"{LUARMOR_BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users"
        headers = {"Authorization": LUARMOR_API_KEY, "Content-Type": "application/json"}
        payload = {"discord_id": discord_id}

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("success") and data.get("user_key"):
                new_key = data["user_key"]
                script_string = f'script_key="{new_key}";loadstring(game:HttpGet("{LUARMOR_LOADER_URL}"))()'
                await interaction.followup.send(f"Your key has been generated! Here is your script:\n```{script_string}```", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to generate a key. API Error: {data.get('message', 'Unknown error.')}", ephemeral=True)
        except requests.exceptions.RequestException as e:
            print(f"Error generating key for user {discord_id}: {e}")
            await interaction.followup.send("An API error occurred while generating your key.", ephemeral=True)

    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.primary, custom_id="persistent_view:reset_hwid")
    async def reset_hwid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        discord_id = str(interaction.user.id)
        user_data = await get_user_by_discord_id(discord_id)

        if not user_data or not user_data.get("user_key"):
            await interaction.followup.send("Could not find a key linked to your Discord account. Please get a script first.", ephemeral=True)
            return

        user_key = user_data["user_key"]
        url = f"{LUARMOR_BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users/resethwid"
        headers = {"Authorization": LUARMOR_API_KEY}
        payload = {"user_key": user_key}

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                embed = discord.Embed(
                    title="✅ HWID Reset Successfully!",
                    description="Your HWID has been reset. The new HWID will be assigned the next time you run the script.",
                    color=discord.Color.gold()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to reset HWID. Reason: {data.get('message', 'Unknown error.')}", ephemeral=True)
        except requests.exceptions.RequestException as e:
            print(f"Error resetting HWID for user {discord_id}: {e}")
            await interaction.followup.send("An API error occurred while resetting your HWID.", ephemeral=True)

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True # Needed for role checks
bot = commands.Bot(command_prefix="!", intents=intents)

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    bot.add_view(ScriptPanelView())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        print("Persistent views registered.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# --- HELPER FUNCTIONS ---
async def get_user_by_discord_id(discord_id: str):
    url = f"{LUARMOR_BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users"
    headers = {"Authorization": LUARMOR_API_KEY, "Content-Type": "application/json"}
    params = {"discord_id": discord_id}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("success") and data.get("users"):
            return data["users"][0]
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user by Discord ID: {e}")
        return None

# --- SLASH COMMANDS ---
@bot.tree.command(name="my_info", description="Get your Luarmor key and script details.")
async def my_info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    discord_id = str(interaction.user.id)
    user_data = await get_user_by_discord_id(discord_id)
    if not user_data:
        await interaction.followup.send("Could not find a Luarmor key linked to your Discord account. Please redeem a key first.", ephemeral=True)
        return
    embed = discord.Embed(title="Your Luarmor Account Info", description="Here are the details linked to your Discord account.", color=discord.Color.blue())
    embed.add_field(name="User Key", value=f"```{user_data.get('user_key', 'N/A')}```", inline=False)
    embed.add_field(name="Status", value=user_data.get('status', 'N/A').capitalize(), inline=True)
    embed.add_field(name="Total Executions", value=user_data.get('total_executions', 'N/A'), inline=True)
    expiry = user_data.get('auth_expire', -1)
    expiry_text = "Never" if expiry == -1 else f"<t:{expiry}:F>"
    embed.add_field(name="Expires", value=expiry_text, inline=True)
    embed.set_footer(text="Use /my_scripts to see your available scripts.")
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="my_scripts", description="Lists all scripts you have access to.")
async def my_scripts(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    url = f"{LUARMOR_BASE_URL}/keys/{LUARMOR_API_KEY}/details"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            await interaction.followup.send(f"API Error: {data.get('message', 'Unknown error.')}", ephemeral=True)
            return
        projects = data.get("projects", [])
        project_scripts = next((p.get("scripts", []) for p in projects if p.get("id") == LUARMOR_PROJECT_ID), None)
        if not project_scripts:
            await interaction.followup.send("You do not have access to any scripts in this project.", ephemeral=True)
            return
        embed = discord.Embed(title="Available Scripts", description="Here are all the scripts you can use:", color=discord.Color.green())
        for script in project_scripts:
            embed.add_field(name=script.get('script_name', 'Unnamed Script'), value=f"FFA: {'Yes' if script.get('ffa') else 'No'}", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching scripts: {e}")
        await interaction.followup.send("An error occurred while trying to fetch script details.", ephemeral=True)

@bot.tree.command(name="reset_hwid", description="Resets the HWID linked to your key.")
async def reset_hwid(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    discord_id = str(interaction.user.id)
    user_data = await get_user_by_discord_id(discord_id)
    if not user_data or not user_data.get("user_key"):
        await interaction.followup.send("Could not find a Luarmor key linked to your Discord account to reset.", ephemeral=True)
        return
    user_key = user_data["user_key"]
    url = f"{LUARMOR_BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users/resethwid"
    headers = {"Authorization": LUARMOR_API_KEY}
    payload = {"user_key": user_key}
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            embed = discord.Embed(title="✅ HWID Reset Successfully!", description="Your HWID has been reset. The new HWID will be assigned the next time you run the script.", color=discord.Color.gold())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to reset HWID. Reason: {data.get('message', 'Unknown error.')}", ephemeral=True)
    except requests.exceptions.RequestException as e:
        error_message = "An internal error occurred while communicating with the API."
        await interaction.followup.send(f"Error: {error_message}", ephemeral=True)

# --- ADMIN COMMANDS ---
@bot.tree.command(name="panelsend", description="[Admin] Sends the script panel to the current channel.")
@app_commands.checks.has_permissions(administrator=True)
async def panelsend(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Script Panel",
        description="Click the buttons below to get your script or manage your account.",
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text="Note: You must have the required role to use these buttons.")
    await interaction.channel.send(embed=embed, view=ScriptPanelView())
    await interaction.response.send_message("Panel sent successfully!", ephemeral=True)

@bot.tree.command(name="generate_key", description="[Admin] Generate a new Luarmor user key.")
@app_commands.describe(days="Number of days the key will be valid for (optional).", note="A note to attach to the key (optional).", user="The Discord user to link this key to immediately (optional).")
@app_commands.checks.has_permissions(administrator=True)
async def generate_key(interaction: discord.Interaction, days: int = None, note: str = None, user: discord.User = None):
    await interaction.response.defer(ephemeral=True)
    url = f"{LUARMOR_BASE_URL}/projects/{LUARMOR_PROJECT_ID}/users"
    headers = {"Authorization": LUARMOR_API_KEY, "Content-Type": "application/json"}
    payload = {}
    if days: payload["key_days"] = days
    if note: payload["note"] = note
    if user: payload["discord_id"] = str(user.id)
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            new_key = data.get("user_key")
            embed = discord.Embed(title="✅ Key Generated Successfully!", color=discord.Color.dark_green())
            embed.add_field(name="New User Key", value=f"```{new_key}```", inline=False)
            description_lines = [f"Expires in: **{days} day(s)** after first use." if days else "Expires: **Never**"]
            if note: description_lines.append(f"Note: `{note}`")
            if user: description_lines.append(f"✅ Automatically linked to: {user.mention}")
            else: description_lines.append("This key is unassigned.")
            embed.description = "\n".join(description_lines)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"Failed to generate key. Reason: {data.get('message', 'Unknown error.')}", ephemeral=True)
    except requests.exceptions.RequestException as e:
        await interaction.followup.send("An error occurred while communicating with the API.", ephemeral=True)

# --- ERROR HANDLING ---
@bot.event
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have the required permissions to run this command.", ephemeral=True)
    else:
        print(f"Unhandled command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
        else:
            await interaction.followup.send("An unexpected error occurred.", ephemeral=True)

# --- RUN THE BOT ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE" or \
       LUARMOR_API_KEY == "YOUR_LUARMOR_API_KEY_HERE" or \
       LUARMOR_PROJECT_ID == "YOUR_LUARMOR_PROJECT_ID_HERE":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: Please fill in your credentials in the script. !!!")
        print("!!! The script will now try to run using environment variables. !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    
    # Check if the critical environment variables are loaded
    if not all([os.environ.get("DISCORD_TOKEN"), os.environ.get("LUARMOR_API_KEY"), os.environ.get("PROJECT_ID")]):
         print("CRITICAL ERROR: One or more required environment variables (DISCORD_TOKEN, LUARMOR_API_KEY, PROJECT_ID) are not set.")
    else:
        bot.run(os.environ.get("DISCORD_TOKEN"))

