import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv

# =========================================================
# Environment Variables
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
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Role that can generate keys
AUTHORIZED_ROLE_ID = 1405035087703183492

# In-memory storage for user keys (use a DB in production)
user_keys = {}

# Predefined key list
KEYS = [
    "QUvgeRZzlAKhjHjghbSvGtfcoluRRfoL",
    "wWbpswiGsTFfcLFxzxjkkrTLYFwUidWW",
    "TIEGWKiEhEjRXdHqUkhyiKIAZcChdKZz",
    "bNBDNVuVrFQdwrqKMWNohByxnYziYIkY",
    "DlyhHTIyyDrXoAjXmtDoOnDHdlNsxPir",
    "jirPzvvkLESISKXlqSlUslCutMaICSYN",
    "sOTBENfqtbYEuddiYWbbVPJufuUVvxAp",
    "heDxGEEUBMAcTHgDfZFutPKNVRXTCmJZ",
    "bXUreDnKPuqetHKIFxXTmCnlUEkTObSw",
    "RZmYLiPzhwWnPTrNdwXasZnFCxvGHldI",
    "eRvzBZWZEFAqhoMPRIuPhyOtErEavUVb",
    "KpgCWTobOvPBhTRwgVKjBaHeYpndGitp",
    "AxQlbnLPGmULhuoZetPafiumnEmVOhxn",
    "RZDZFfKvwyQboGmDfmoYckdDIXgACxks",
    "sZriZsjKzXStSdfRqwWKCyCamAKJYpzX",
    "ilTjqHYaMvLsidGxPNhhoKnLjvWNJmfD",
    "pbGfvXIrexDxPrhMgnDkICBPxQyCVqgP",
    "RrxMlYEGVbdPDjWsSAOdmjXiXNVMzvoz",
    "KpjVrMrqMEQboBksrupMKkEwXMZBgahX",
    "oaKwiekvdqfhGkajPxTUoIDEEKjbyTEN",
    "KjwucKnVNeMECYFObDYpcxwBqDTDqSsK",
    "dUbLMXXuNJkKKRVJTIENQaFiNlsOqxZV",
    "XlkHTlxEFtAmqonmfuhctyKvCdgKfgNn",
    "WFkGBkARzouQljvVAQSZPMjwhFFkFwup",
    "CvLKcswwTUmrzcffjTzwdhMUrInodrLS",
    "feXQqQEJETMWKwGLrHkrrhmSVTuzFDuw",
    "tgviIUVKdRISmIuNHuSVtgWRNbsEzzUa",
    "BPiMDxKxNvXphkuQZOegOiAIqyZDYVuZ",
    "ugzAbdEJccFqtGZlphSvsHIjgDsxvHcY",
    "HXpfZEVKGSStQbtVYyldLIGamRKgmCAa",
    "dBxoVcxhCRTQHYlesOhCCpjhHxSkpDaN",
    "XxMpCtTkXRhRjFjOGQRvxIVaZrSQvHWg",
    "KsinEGxjTNTwISyVufElNEGyFpTWZpgq",
    "ggIaKmmFmIcGUpleyhLRJUIKxWWTrakm",
    "jpWhxYPoHLTIWycALFLtKzhmBBpbztBn",
    "dZXnihomGtnDzgXDTBwqlJMfSlfoCjuL",
    "jBHKYDLIpgdgGeyodzyZNpiaGkinXSxd",
    "WDOMoXuxDZvNEcZqYevzrdalugrgXsWA",
    "kMjcVsABvdofaFPyJAYXLHfetlzGJQzH",
    "IWJNVMJeZQmArEtihksAXDXkovmmhmPH",
    "ESUFXJrTebvHjkyCXbHTVyNbhOVgOVct",
    "dmmkMWtnLufHeiWuwCBjQCxebfRYVdkG",
    "xyQOzZIrTWWpuduKSBhJSoirCkkCiakz",
    "waXfIGipAgGYyMvZccLtWhTPhPZidycm",
    "RkYChLieIAMnFHWPAhiyZZSijcKyDywY",
    "GIhigIBlFeJWERfXqknAhOoKrDsHsaVH",
    "JMbtSBzeKIgnfpApkJKgyqmaJXQzvFYR",
    "iolszOUtfmjpJUTkqgxtOQXdvPUyhCCH",
    "uZdDHPfreKfncOTCEhqDjgyrLjqeDVTJ",
    "tqXEDVCPfPogCrnInMLASKuGdPOcAPDL",
    "EwmrIFObpXRJazvZKOwGRkZxHUWXUCfC",
    "jvNQejNBmkTsjGndcfYQAduOsaHahMnJ",
    "XifvQJQSRKqVgiNPtlQcLWJZqGdfuXIF",
    "oWvfJufZvzZuRyoGKeXntLjsnorzcSqR",
    "bMYVZGLpdWcDzfPMJybimJVVEPkLnpct",
    "mYkWgKeJhYMCTZAVrxDspxCTzEwkqcUa",
    "uHBcREETrCZWnIAXVodERKYrGJLeiRGE",
    "BDNemopWJbpPDGJGeqkenlEzerQWlCdX",
    "SHIAlkhsiHagVgoxYEbnEmYvpkZdToKx",
    "UFZXmbjwPCqbTTlkfofEnXrwZLDSrXiE",
    "BjlHDhvdxGalqURAYDWSySQmHNKFZJjx",
    "pZPVDhvvngRVgggbrdKaTshGTktSKXCC",
    "tGeVXzwPJNevIjELCFeUvrELhlZLSMUt",
    "fFHrrNARJqcaPTHCRpqItjSlkmYAkYOn",
    "eCGbElLXXKJXdqOXqtBqoIRQuMwlYcYq",
    "BCQpZoEiBBDJGSPhuqSurnHtEFuWKHII",
    "szLmoGmzPgwqRDiVxWYnwmAzaWmKWLrW",
    "XdKSfEEEwXMVmqBbMftsmhYeppxwlXFX",
    "jalAVNsVzbZGoDhOjHsaoiDURULSrkZQ",
    "xsNeadKIBBQmMsLXnqgMdedDGHxDgTHl",
    "jzmXZSKOpeMdGvyaeTMpaeZwrjTFxIhn",
    "eSUWfBWEjXjSppAdNsImtGOiJjuMMLNo",
    "YgcgjfjmEUQOYJrNosEfBvRCZsWcJuMw",
    "ySxWQbkiJFBwdiQTwGbcHGgIGxzrRRBY",
    "eUPyQSOTOhkRLSMUPuiBcpBkwUfnNcZA",
    "gOuQrohzDJaHYHkFErBYBzhHcTqiomeG",
    "cgyzgvsvEevPxKTABxUcPXKuQUrNvnOI",
    "EwvIxnoboEaQTKhmxouAQPvNXDIEUcYI",
    "okImhBkschjuaChpdGEqnbcBxpWMvopU",
    "ZWhxrDrSkMeCIBYTWMVKZUcXJpNNebhG",
    "mWMUESLxfaLkrhGOuMuhRsiBQzJcnJwn",
    "UTgOdziYSsfHtSQbWCJfqxehrntFZnXa",
    "RGFIrtvUwXEvdaPKkESdlMKjBoEYRyEw",
    "yljkaUlVVdKcKHubqeAmUfehLxQkgTMw",
    "bqKUlkREfgurVCjyMbkCSOMUGRklrONZ",
    "atKTJiMiiTukDuBmQCAXxqUvQMUOkvvt",
    "tGSxyiswBHlScaxYxkLvSgOEUtCrVNeZ",
    "hpcjklkGUpkFlZhLkmQaLFGzNIwsUuGg",
    "UKCCYhvYpNuOqwkzKQyhZVcaPkKPCboe",
    "kYSHKNsbHQLpHBFIYlOBzoKlKwKsSgNW",
    "XFSYQyysaLAFvtvAeXiWYlUIijUBnaKu",
    "EHQJfgqOxToTtkznLOBYFOGxIEYOuyas",
    "eTSOauhzDaFQaTvbqODuFMcQlsHCvtwo",
    "sLgfIJSJHNGpaAJIyrLQbLXfnGGtqcAa",
    "HcREEIRcBDopkauBwuOOGtgLphSDCCIk",
    "gVWLSmGyuNPRCTIqORdhwSWUCjCWxWJT",
    "vOSAWwPSPPPQXZeOCyRKJUPMwfbIReZk",
    "czQMBdxZWlOaXEUjkOXHcLPoZcDUHyiV",
    "OfngloCvrxywRFkUjMKyegfujfVsdsTh",
    "QBjvLhYwexsqVZkFCpEjdkIzgTpJamrN",
    "RpinLWTQUbuSIJrUKUOQTvAZHOIaFBds",
    "qDckKEMnPPJmlyssodJHQYzYZhXABjMt",
    "xfDYwQDdgqubRRsMkOvSuIOAVwJciWNP",
    "BeAJraGBuOpyymRtlsCLUcWPWsxbvDYk",
    "RausdeCmkQdxsCRyJmdPPIlJPUCGFcZd",
    "bMjunATwpYIvuKCqnIkGqKtRKBuwXioq",
    "FqvPttCMWPXvWBUNBOvklqdKmIiAFByk",
    "KtUujDdjuMEQLBAEsbqYXBoagnMtXIyc",
    "vksskhbLxFVsCrWBJwrENrStWZKOeLzA",
    "GgrviATeBRcQzyrYMNzOIUEJUsfgRSSJ",
    "VwpxGTIHjAlalEvVTQQfHxmoFdITjLql",
    "yGMOZrFBmIkNzOlpXXjUwOPJUVpqmJWN",
    "HgQdlrDAhalkAdteTbIqQzPzZHdACTjg",
    "ZVTFkcWpIigjyrTAjKilkZyYqipYWXwA",
    "SoErTTMGNxkWLXtCpQgRHjubeKFMlzjd",
    "UaOaYdoQyRMNNLcgqceyOTmUoLpaZCIm",
    "WawEuGcXCrzDhRALRrLICkWgynsmAaRt",
    "ELGKhDNISQDNdXzTbSQcRqsNABKmbMGa",
    "RctFBjEDvYXvYGhQvrSLQtNkIbwyaHCL",
    "bPsTunvWFnYffAXczAfTRWLSGImJIQRq",
    "DaIDnmZbhQRrkHWBRsIBkchZeZZkOnQl",
    "VuJgEfQhfuCHcfZaHafbgcITcCNfuppN",
    "qsaUMWcLYUiYfQKRNkajRtsjxXXTGGez",
    "TTObxrGuJoeXgmxWVpOJyTpKSGqviWMu",
    "uHWplqyosYSbFcdFXJmiJKFErsbZZmlL",
    "udjoRolGdqeZZmFrsZnWxJCQTZTBirxm",
    "EyGhIDPsbLOeiwQcGZyrnTuGMbonLUPy",
    "wfTgWkvFlfPslaiLnZicVPazTjypxdKk",
    "xKpMxNxTSydGSThGQpdDMIpmQszwxZff",
    "nESXUxINVOKdbpVVHjzNxEfgQTXpkGhx",
    "ErniGwArsOvlZGTBtasILaFxFlRONeMf",
    "dgasiQkImDccWljhKcBNhCuyJRYjVNRS",
    "NlPYKzmWtLYRtTOIGuKURzVdRsJSYSGv",
    "xgGBYmWwEqpsbtIDqSiklieCyXAuKNOb",
    "SqgWlJdgxUHrQofBvFKlAcZgyUKkqUiy",
    "dtwkIgRJNUwJbPIVlhkPPHHttJnWYGOo",
    "tsNygdioPseqmftMVyVZioRVZspZvuUu",
    "jYSwTxKLaCCkCqVXdbDEYUObYTMIbaTN",
    "eoJYmDAUWMBgmNaEjJTGkwzoPYUcrSOX",
    "ZaCwFwbbRSTmvqIqNtFjFncAAOOiDQbb",
    "lBYmEGMRdufSTnmmcYJPBUYtWolWWWBu",
    "QjDstGhXTJGLPYQWkqBgZACdloUzhTsF",
    "vgAODhbcKGthXJKffmrvwlVnSZkaLsUM",
    "IoJfhrpFvHhEIwIJPhSccSExAUrCuVfu",
    "hCkKFSiDYWjCtTIIHELJAxRToQCFkZuc",
    "bJnsRXOBYdVRSCfNgEgPhMlfsLcnsTeB",
    "abeLYGYXBYNhcNELPahuQtoEQeUqKcjv",
    "kBDdrgVpPMZbonHLjqSnmsSITHRVfYOl",
    "lTFXBjIikbIxKwfoVRCAWTsVHPEDEJRc",
    "BUbamkbtaHZGKOXhDYdOEdxOEzBeAZNp",
    "deTnXHbRerXMVmxMdubpTUTCmFsClaFA"
]

# =========================================================
# Helper Functions
# =========================================================

def generate_key(user_id: int) -> str:
    if user_id in user_keys:
        return user_keys[user_id]
    key = random.choice(KEYS)
    user_keys[user_id] = key
    return key

def reset_key(user_id: int) -> bool:
    if user_id in user_keys:
        del user_keys[user_id]
        return True
    return False

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
# Slash Commands
# =========================================================

@bot.tree.command(name="generatekey", description="Generate a key linked to your user ID.")
async def generate_key_command(interaction: discord.Interaction):
    user = interaction.user
    role_ids = [role.id for role in getattr(user, 'roles', [])]
    if AUTHORIZED_ROLE_ID not in role_ids:
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.", ephemeral=True
        )
        return

    key = generate_key(user.id)
    await interaction.response.send_message(
        f"🔑 Your key is: `{key}`\nIt is now linked to your account.",
        ephemeral=True
    )

# Reset Key Button
class ResetKeyView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Reset Key", style=discord.ButtonStyle.danger)
    async def reset_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🚫 You cannot reset someone else's key.", ephemeral=True)
            return

        success = reset_key(self.user_id)
        if success:
            await interaction.response.send_message("✅ Your key has been reset.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You don't have a key to reset.", ephemeral=True)

@bot.tree.command(name="resetkey", description="Reset your generated key.")
async def reset_key_command(interaction: discord.Interaction):
    view = ResetKeyView(interaction.user.id)
    await interaction.response.send_message(
        "Click the button below to reset your key:",
        view=view,
        ephemeral=True
    )

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
