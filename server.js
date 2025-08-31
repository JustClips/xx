import "dotenv/config";
import {
  Client,
  GatewayIntentBits,
  Partials,
  Events,
  PermissionsBitField
} from "discord.js";

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const CHANNEL_ID = "1410395105965375600"; // Fixed target channel

if (!DISCORD_TOKEN) {
  console.error("Missing DISCORD_TOKEN environment variable.");
  process.exit(1);
}

// Toggle state (default active = true so it works immediately; change to false if you prefer)
let active = true;

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

]; // Leave empty for dynamic generation each message

// Optional: set true to cycle sequentially through provided NICKNAMES (only matters if list not empty)
const SEQUENTIAL = false;

let seqIndex = 0;
const lastNicknameByUser = new Map();
const inFlight = new Map();

// Word pools for dynamic nickname generation when NICKNAMES is empty
const RAND_ADJ = [
  "Flux","Neon","Nova","Quantum","Hyper","Turbo","Pixel",
  "Zesty","Meta","Ultra","Astro","Cyber","Glitch","Lunar",
  "Vortex","Binary","Cosmic","Proto","Omega","Solar"
];
const RAND_CORE = [
  "Spark","Drift","Pulse","Shard","Shift","Core","Node","Loop",
  "Hex","Ray","Wave","Arc","Frame","Phase","Trace","Grid","Beam"
];

function generateDynamicNick() {
  const adj = RAND_ADJ[Math.floor(Math.random() * RAND_ADJ.length)];
  const core = RAND_CORE[Math.floor(Math.random() * RAND_CORE.length)];
  const tail = Math.random().toString(36).slice(2, 6); // 4 chars
  const variant = Math.floor(Math.random() * 900 + 100); // 3 digits
  return `${adj}${core}-${tail}${variant}`.slice(0, 32);
}

function nextNickname(userId) {
  // If list provided
  if (NICKNAMES.length > 0) {
    if (SEQUENTIAL) {
      const nick = NICKNAMES[seqIndex % NICKNAMES.length];
      seqIndex++;
      lastNicknameByUser.set(userId, nick);
      return nick.slice(0, 32);
    }
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

  // Dynamic mode
  for (let i = 0; i < 5; i++) {
    const nick = generateDynamicNick();
    if (lastNicknameByUser.get(userId) !== nick) {
      lastNicknameByUser.set(userId, nick);
      return nick;
    }
  }
  const fallback = generateDynamicNick();
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
  console.log(`Channel: ${CHANNEL_ID}`);
  console.log(`Active on start: ${active}. Use !stop or !start in the channel (Manage Server required).`);
});

async function setNickname(member, newNick) {
  const me = member.guild.members.me;
  if (!me) return;
  if (!me.permissions.has(PermissionsBitField.Flags.ManageNicknames)) return;
  if (!(me.roles.highest.comparePositionTo(member.roles.highest) > 0)) return;

  const trimmed = newNick.slice(0, 32);
  try {
    await member.setNickname(trimmed, "Per-message nickname change");
  } catch {
    // Ignore errors (permissions, rate limit, hierarchy)
  }
}

client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (message.channel.id !== CHANNEL_ID) return;

  const content = message.content.trim().toLowerCase();

  // Command: !stop
  if (content === "!stop") {
    if (!message.member.permissions.has(PermissionsBitField.Flags.ManageGuild)) {
      message.reply("You lack permission (Manage Server required).").catch(() => {});
      return;
    }
    if (!active) {
      message.reply("Already stopped.").catch(() => {});
      return;
    }
    active = false;
    message.reply("Nickname changing DISABLED.").catch(() => {});
    return;
  }

  // Command: !start
  if (content === "!start") {
    if (!message.member.permissions.has(PermissionsBitField.Flags.ManageGuild)) {
      message.reply("You lack permission (Manage Server required).").catch(() => {});
      return;
    }
    if (active) {
      message.reply("Already active.").catch(() => {});
      return;
    }
    active = true;
    message.reply("Nickname changing ENABLED.").catch(() => {});
    return;
  }

  if (!active) return;

  const member = message.member;
  if (!member) return;

  // Prevent overlapping edits if user spam messages quickly
  if (inFlight.get(member.id)) return;
  inFlight.set(member.id, true);
  try {
    const nick = nextNickname(member.id);
    await setNickname(member, nick);
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
