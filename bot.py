import os
import sys
import traceback
import logging
from typing import Optional, List
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp

# =========================================================
# Logging
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
log = logging.getLogger("eps1llon-bot")

# =========================================================
# MySQL Connector Import
# =========================================================
try:
    import mysql.connector
    from mysql.connector import Error, pooling
    MYSQL_CONNECTOR_AVAILABLE = True
except ImportError:
    MYSQL_CONNECTOR_AVAILABLE = False
    log.warning("mysql-connector-python NOT installed. Using in-memory fallback.")

# =========================================================
# Environment Variables
# =========================================================
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
if not LUARMOR_API_KEY or not PROJECT_ID:
    log.warning("Missing LUARMOR_API_KEY or PROJECT_ID (Luarmor actions may fail).")

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    raise SystemExit("CHANNEL_ID must be an integer.")

# =========================================================
# STATIC KEY POOL (SEED LIST)
# =========================================================
# These are the unused keys you provided. They will be inserted into the DB (available_keys table)
# ONLY if the table is empty on startup. After first seed, REMOVE or COMMENT OUT this list for safety.
KEYS_SEED = [
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
# In-memory fallback structures
# =========================================================
user_keys_memory = {}          # discord_id -> key
user_reset_counts = {}         # discord_id -> int
available_keys_memory = KEYS_SEED.copy()
assigned_keys_memory = set()

# =========================================================
# Storage Manager
# =========================================================
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
                log.info("MySQL pool created.")
                self.create_tables()
                self.seed_available_keys(KEYS_SEED)
            except Error as e:
                log.error(f"MySQL pool init failed: {e}")
                self.using_mysql = False
        else:
            if not MYSQL_CONNECTOR_AVAILABLE:
                log.info("MySQL connector missing; using memory.")
            else:
                log.info("MySQL env vars incomplete; using memory.")

    def get_connection(self):
        if not self.using_mysql or not self.pool:
            return None
        try:
            return self.pool.get_connection()
        except Error as e:
            log.error(f"Pool get_connection error: {e}")
            return None

    def create_tables(self):
        conn = self.get_connection()
        if not conn:
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS available_keys (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    license_key VARCHAR(64) UNIQUE NOT NULL,
                    assigned_to BIGINT NULL,
                    assigned_at TIMESTAMP NULL,
                    INDEX idx_license_key (license_key),
                    INDEX idx_assigned_to (assigned_to)
                )
            """)
            conn.commit()
            log.info("Ensured tables user_keys & available_keys exist.")
            cur.close()
        except Error as e:
            log.error(f"Error creating tables: {e}")
            self.using_mysql = False
        finally:
            try:
                conn.close()
            except:
                pass

    def seed_available_keys(self, keys: List[str]):
        """
        Insert seed keys only if available_keys table is empty.
        """
        if not self.using_mysql:
            # Memory mode already has available_keys_memory pre-loaded
            return
        conn = self.get_connection()
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM available_keys")
            count = cur.fetchone()[0]
            if count == 0:
                log.info(f"Seeding {len(keys)} license keys...")
                data = [(k,) for k in keys]
                cur.executemany(
                    "INSERT IGNORE INTO available_keys (license_key) VALUES (%s)",
                    data
                )
                conn.commit()
                log.info("Seed complete.")
            else:
                log.info("available_keys table already has data; skipping seed.")
            cur.close()
        except Error as e:
            log.error(f"Seeding error: {e}")
        finally:
            conn.close()

    # -------- User key functions --------
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
                log.error(f"get_user_key error: {e}")
                return user_keys_memory.get(discord_id, "")
            finally:
                conn.close()
        else:
            return user_keys_memory.get(discord_id, "")

    def save_user_key(self, discord_id: int, user_key: str):
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                user_keys_memory[discord_id] = user_key
                return
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO user_keys (discord_id, user_key)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE user_key = VALUES(user_key)
                """, (discord_id, user_key))
                conn.commit()
                cur.close()
            except Error as e:
                log.error(f"save_user_key error: {e}")
                user_keys_memory[discord_id] = user_key
            finally:
                conn.close()
        else:
            user_keys_memory[discord_id] = user_key

    def allocate_static_key(self, discord_id: int) -> Optional[str]:
        """
        Allocate an unused static key to the user (if they don't already have one).
        Returns the key or None if none available.
        """
        existing = self.get_user_key(discord_id)
        if existing:
            return existing

        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                # fallback memory
                return self._allocate_key_memory(discord_id)
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT license_key FROM available_keys
                    WHERE assigned_to IS NULL
                    ORDER BY id ASC
                    LIMIT 1
                """)
                row = cur.fetchone()
                if not row:
                    cur.close()
                    return None
                key = row[0]
                cur.execute("""
                    UPDATE available_keys
                    SET assigned_to = %s, assigned_at = CURRENT_TIMESTAMP
                    WHERE license_key = %s
                """, (discord_id, key))
                conn.commit()
                cur.close()
                self.save_user_key(discord_id, key)
                return key
            except Error as e:
                log.error(f"allocate_static_key error: {e}")
                return None
            finally:
                conn.close()
        else:
            return self._allocate_key_memory(discord_id)

    def _allocate_key_memory(self, discord_id: int) -> Optional[str]:
        for k in list(available_keys_memory):
            if k not in assigned_keys_memory:
                assigned_keys_memory.add(k)
                user_keys_memory[discord_id] = k
                return k
        return None

    def increment_reset_count(self, discord_id: int):
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                user_reset_counts[discord_id] = user_reset_counts.get(discord_id, 0) + 1
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
                user_reset_counts[discord_id] = user_reset_counts.get(discord_id, 0) + 1
            finally:
                conn.close()
        else:
            user_reset_counts[discord_id] = user_reset_counts.get(discord_id, 0) + 1

    def stats(self) -> dict:
        if self.using_mysql:
            conn = self.get_connection()
            if not conn:
                return {"using_mysql": True, "reachable": False, "rows": None, "unused_keys": None}
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM user_keys")
                user_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM available_keys WHERE assigned_to IS NULL")
                unused = cur.fetchone()[0]
                cur.close()
                return {
                    "using_mysql": True,
                    "reachable": True,
                    "rows": user_count,
                    "unused_keys": unused
                }
            except Error as e:
                log.error(f"stats error: {e}")
                return {"using_mysql": True, "reachable": False, "rows": None, "unused_keys": None}
            finally:
                conn.close()
        else:
            unused = len([k for k in available_keys_memory if k not in assigned_keys_memory])
            return {
                "using_mysql": False,
                "reachable": True,
                "rows": len(user_keys_memory),
                "unused_keys": unused
            }

storage = StorageManager()

# =========================================================
# Discord Bot Setup
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

AUTHORIZED_ROLE_ID = 1405035087703183492  # Replace with your real role ID

# =========================================================
# Luarmor API (still used for HWID reset)
# =========================================================
async def reset_user_hwid(user_key: str) -> bool:
    if not (LUARMOR_API_KEY and PROJECT_ID):
        log.warning("Luarmor credentials missing; cannot reset HWID.")
        return False
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
                log.error(f"Luarmor reset error {response.status}: {body}")
            return response.status == 200

# =========================================================
# Events
# =========================================================
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} command(s).")
    except Exception as e:
        log.error(f"Command sync failed: {e}")

# =========================================================
# View (Buttons)
# =========================================================
class PremiumPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Generate Key", style=discord.ButtonStyle.success, custom_id="generate_key")
    async def generate_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role_ids = [r.id for r in getattr(interaction.user, "roles", [])]
            if AUTHORIZED_ROLE_ID not in role_ids:
                await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
                return

            existing = storage.get_user_key(interaction.user.id)
            if existing:
                await interaction.response.send_message("⚠️ You already have a key. Use 'Get Script'.", ephemeral=True)
                return

            key = storage.allocate_static_key(interaction.user.id)
            if not key:
                await interaction.response.send_message("❌ No keys available. Contact an admin.", ephemeral=True)
                return

            await interaction.response.send_message(
                "✅ Key assigned! Use 'Get Script' to retrieve your loader script.",
                ephemeral=True
            )
        except Exception as e:
            log.error(f"generate_key error: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary, custom_id="get_script")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role_ids = [r.id for r in getattr(interaction.user, "roles", [])]
            if AUTHORIZED_ROLE_ID not in role_ids:
                await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
                return

            key = storage.get_user_key(interaction.user.id)
            if not key:
                await interaction.response.send_message("❌ You don't have a key yet. Press 'Generate Key'.", ephemeral=True)
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
            role_ids = [r.id for r in getattr(interaction.user, "roles", [])]
            if AUTHORIZED_ROLE_ID not in role_ids:
                await interaction.response.send_message("❌ You do not have permission.", ephemeral=True)
                return

            key = storage.get_user_key(interaction.user.id)
            if not key:
                await interaction.response.send_message("❌ You don't have a key yet.", ephemeral=True)
                return

            success = await reset_user_hwid(key)
            if success:
                storage.increment_reset_count(interaction.user.id)
                await interaction.response.send_message("✅ HWID reset successful.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ HWID reset failed.", ephemeral=True)
        except Exception as e:
            log.error(f"reset_hwid error: {e}\n{traceback.format_exc()}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Internal error.", ephemeral=True)

# =========================================================
# Slash Commands
# =========================================================
@bot.tree.command(name="sendpanel", description="Send the premium panel to this channel.")
async def send_panel(interaction: discord.Interaction):
    if interaction.user.id != interaction.guild.owner_id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    embed = discord.Embed(
        title="Eps1llon Hub Premium Panel",
        description="Use the buttons below to manage your premium access.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="Instructions",
        value=(
            "1. Generate Key\n"
            "2. Get Script\n"
            "3. Reset HWID (if needed)"
        ),
        inline=False
    )
    embed.set_footer(text="Eps1llon Hub Premium")
    view = PremiumPanelView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Panel sent.", ephemeral=True)

@bot.tree.command(name="dbstatus", description="Show DB/key status (admins only).")
async def dbstatus(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    stats = storage.stats()
    msg = (
        f"Using MySQL: {stats['using_mysql']}\n"
        f"Reachable: {stats['reachable']}\n"
        f"Assigned user rows: {stats['rows']}\n"
        f"Unused keys remaining: {stats['unused_keys']}"
    )
    await interaction.response.send_message(f"```{msg}```", ephemeral=True)

# =========================================================
# Entrypoint
# =========================================================
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
