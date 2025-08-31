import "dotenv/config";
import {
  Client,
  GatewayIntentBits,
  Partials,
  Events,
  PermissionsBitField
} from "discord.js";

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;

// Fixed channel
const CHANNEL_ID = "1410395105965375600";
const CHANNEL_ONLY = true; // set false to apply in all channels

// Optional: set to a specific user ID (string). If empty = everyone in the channel(s).
const TARGET_USER_ID = ""; // e.g. "123456789012345678"

// Empty list as requested. If you later add entries, the bot will pick from them randomly.
// While this stays empty, a generated random nickname is used each message.
const NICKNAMES = [
 "big cock rider",
"dildo enjoyer",
"cock rider",
"pulsar bitch",
"i bark for free",
"dm for blowjob",
"mongoloid",
"im a zesty kid",
"dick enjoyer",
"i love white liquid",
"sucking dick for 10$",
"real monkey",
"monkey with big dick",
"zesty monkey",
"i love jerkin off",
"dm me for free fuck",
"reverse jerkoff 300",
"barking cat",
"6-7?",
"i will crack yo nuts like a nutcracker",
"feet pics for 10$",
"meow",
"monkey",
"My dih tired",
"MangoMangoMangoMango",
"Six sevennn"

];

// Sequential mode (only applies if you add nicknames). false = random choice from list.
const SEQUENTIAL = false;

if (!DISCORD_TOKEN) {
  console.error("Missing DISCORD_TOKEN environment variable.");
  process.exit(1);
}

// State
let seqIndex = 0;
const lastNicknameByUser = new Map();
const inFlight = new Map(); // prevent overlapping edits per user

// Random components for generator
const RAND_ADJ = [
  "Flux","Neon","Nova","Quantum","Hyper","Turbo","Pixel",
  "Zesty","Meta","Ultra","Astro","Cyber","Glitch","Lunar",
  "Vortex","Binary","Cosmic","Proto","Omega","Solar"
];
const RAND_CORE = [
  "Spark","Drift","Pulse","Shard","Shift","Core","Node","Loop",
  "Hex","Ray","Wave","Arc","Frame","Phase","Trace","Grid","Beam"
];

// Generate a nickname when list empty
function generateDynamicNick() {
  const adj = RAND_ADJ[Math.floor(Math.random() * RAND_ADJ.length)];
  const core = RAND_CORE[Math.floor(Math.random() * RAND_CORE.length)];
  // random alphanumeric segment
  const tail = Math.random().toString(36).slice(2, 6); // 4 chars
  const variant = Math.floor(Math.random() * 900 + 100); // 3 digits
  return `${adj}${core}-${tail}${variant}`;
}

function nextNickname(userId) {
  if (NICKNAMES.length === 0) {
    // purely dynamic
    for (let i = 0; i < 5; i++) {
      const nick = generateDynamicNick();
      if (lastNicknameByUser.get(userId) !== nick) {
        lastNicknameByUser.set(userId, nick);
        return nick.slice(0, 32);
      }
    }
    const fallback = generateDynamicNick().slice(0, 32);
    lastNicknameByUser.set(userId, fallback);
    return fallback;
  }

  if (SEQUENTIAL) {
    const nick = NICKNAMES[seqIndex % NICKNAMES.length];
    seqIndex++;
    lastNicknameByUser.set(userId, nick);
    return nick.slice(0, 32);
  }

  // Random from provided list
  for (let i = 0; i < 5; i++) {
    const nick = NICKNAMES[Math.floor(Math.random() * NICKNAMES.length)];
    if (lastNicknameByUser.get(userId) !== nick) {
      lastNicknameByUser.set(userId, nick);
      return nick.slice(0, 32);
    }
  }
  const fallback = NICKNAMES[Math.floor(Math.random() * NICKNAMES.length)].slice(0, 32);
  lastNicknameByUser.set(userId, fallback);
  return fallback;
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent
  ],
  partials: [Partials.GuildMember, Partials.User]
});

client.once(Events.ClientReady, () => {
  console.log(`Logged in as ${client.user.tag}`);
  console.log(`Mode: instant per-message nickname change ${CHANNEL_ONLY ? `in channel ${CHANNEL_ID}` : "in all channels"}.`);
  if (TARGET_USER_ID) {
    console.log(`Target limited to user ID: ${TARGET_USER_ID}`);
  } else {
    console.log("Target: ALL users in scope.");
  }
});

/**
 * Attempt nickname change with small retry for transient failures.
 */
async function setNicknameWithRetry(member, newNick) {
  const me = member.guild.members.me;
  if (!me) return;
  if (!me.permissions.has(PermissionsBitField.Flags.ManageNicknames)) return;
  if (!(me.roles.highest.comparePositionTo(member.roles.highest) > 0)) return;

  const trimmed = newNick.slice(0, 32);
  const MAX_ATTEMPTS = 2;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      await member.setNickname(trimmed, "Auto per-message nickname change");
      return;
    } catch (err) {
      // Permissions/hierarchy or explicit refusal -> stop
      if (err?.code === 50013 || err?.status === 403) return;
      if (err?.status === 429) return; // rate-limit
      if (attempt < MAX_ATTEMPTS) {
        await new Promise(r => setTimeout(r, 200));
        continue;
      }
    }
  }
}

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (CHANNEL_ONLY && message.channel.id !== CHANNEL_ID) return;
  if (TARGET_USER_ID && message.author.id !== TARGET_USER_ID) return;

  const member = message.member;
  if (!member) return;

  // simple lock to avoid flooding if user spams
  if (inFlight.get(member.id)) return;
  inFlight.set(member.id, true);
  try {
    const nick = nextNickname(member.id);
    await setNicknameWithRetry(member, nick);
  } finally {
    inFlight.delete(member.id);
  }
});

client.login(DISCORD_TOKEN);

process.on("SIGTERM", () => {
  console.log("Shutting down...");
  client.destroy();
  process.exit(0);
});
