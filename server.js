import os
import random
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# =========================================================
# Environment Variables (ONLY these two are used)
# =========================================================
# DISCORD_TOKEN = your bot token
# CHANNEL_ID    = the numeric text channel ID where behavior applies
# =========================================================

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not DISCORD_TOKEN or not CHANNEL_ID:
    raise SystemExit("Missing DISCORD_TOKEN or CHANNEL_ID environment variables.")

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
intents.members = True  # Needed to change nicknames

bot = commands.Bot(command_prefix="!", intents=intents)
active = False  # Toggled by !start / !stop

# Simple word pools for nickname generation
ADJECTIVES = [
    "Zesty", "Fuzzy", "Icy", "Brave", "Cosmic", "Witty", "Quirky", "Spicy", "Mellow", "Silly",
    "Bouncy", "Glitchy", "Nebula", "Rusty", "Swift", "Snazzy", "Giddy", "Chill", "Dizzy", "Soggy"
]
NOUNS = [
    "Llama", "Otter", "Falcon", "Badger", "Kraken", "Panda", "Mantis", "Cobra", "Pixel", "Comet",
    "Raptor", "Golem", "Lynx", "Phoenix", "Dragon", "Puffin", "Beetle", "Fox", "Aardvark", "Moose"
]

# Track last nickname per user to reduce immediate duplicates
last_nick = {}


def generate_nickname(user_id: int) -> str:
    # Try a few times to avoid repeat
    for _ in range(5):
        adj = random.choice(ADJECTIVES)
        noun = random.choice(NOUNS)
        num = random.randint(100, 999)
        nick = f"{adj}{noun}{num}"
        if last_nick.get(user_id) != nick:
            last_nick[user_id] = nick
            return nick
    # Fallback
    nick = f"Nick{random.randint(0, 99999)}"
    last_nick[user_id] = nick
    return nick


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Watching channel {CHANNEL_ID}. Use !start there to activate.")
    # Try to fetch the channel to verify
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("Warning: Channel not found in cache yet. It will be resolved on first message.")


def has_manage_guild(member: discord.Member) -> bool:
    return member.guild_permissions.manage_guild


@bot.command(name="start")
async def start_cmd(ctx: commands.Context):
    global active
    if ctx.channel.id != CHANNEL_ID:
        return
    if not isinstance(ctx.author, discord.Member):
        return
    if not has_manage_guild(ctx.author):
        await ctx.reply("You lack permission (Manage Server required).", mention_author=False)
        return
    if active:
        await ctx.reply("Already active.", mention_author=False)
        return
    active = True
    await ctx.reply("Per-message nickname changes ACTIVATED.", mention_author=False)


@bot.command(name="stop")
async def stop_cmd(ctx: commands.Context):
    global active
    if ctx.channel.id != CHANNEL_ID:
        return
    if not isinstance(ctx.author, discord.Member):
        return
    if not has_manage_guild(ctx.author):
        await ctx.reply("You lack permission (Manage Server required).", mention_author=False)
        return
    if not active:
        await ctx.reply("Already stopped.", mention_author=False)
        return
    active = False
    await ctx.reply("Per-message nickname changes DISABLED.", mention_author=False)


@bot.event
async def on_message(message: discord.Message):
    # Allow commands to process first / also required for commands to work
    await bot.process_commands(message)

    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return
    if not active:
        return
    if not isinstance(message.author, discord.Member):
        return

    member: discord.Member = message.author

    # Check if bot can manage this member
    if not member.guild.me:  # type: ignore
        return
    if not member.guild.me.guild_permissions.manage_nicknames:  # type: ignore
        return
    if not member.guild.me.top_role > member.top_role:  # type: ignore
        return  # Role hierarchy prevents nickname change

    new_nick = generate_nickname(member.id)
    try:
        await member.edit(nick=new_nick, reason="Per-message nickname change")
    except discord.Forbidden:
        pass  # Missing permission or hierarchy issue
    except discord.HTTPException:
        pass  # Rate limit or other HTTP issue ignored


# Graceful shutdown (optional)
async def shutdown():
    await bot.close()


def main():
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
