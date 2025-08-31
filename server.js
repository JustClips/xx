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

let active = false; // toggled by !start / !stop
const lastNicknameByUser = new Map();

// Zesty / playful nickname pool (safe / non-harassing).
// Feel free to add more entries. Keep them within Discord guidelines.
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

];

// Set true if you want sequential cycling instead of random
const SEQUENTIAL = false;
let seqIndex = 0;

function nextNickname(userId) {
  if (!NICKNAMES.length) return "Nickname";
  if (SEQUENTIAL) {
    const nick = NICKNAMES[seqIndex % NICKNAMES.length];
    seqIndex++;
    lastNicknameByUser.set(userId, nick);
    return nick;
  }
  // Random with small loop to avoid immediate duplicate for that user
  for (let i = 0; i < 5; i++) {
    const nick = NICKNAMES[Math.floor(Math.random() * NICKNAMES.length)];
    if (lastNicknameByUser.get(userId) !== nick) {
      lastNicknameByUser.set(userId, nick);
      return nick;
    }
  }
  // Fallback (just pick one)
  const fallback = NICKNAMES[Math.floor(Math.random() * NICKNAMES.length)];
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
  console.log(`Watching channel ${CHANNEL_ID}. Type !start there (Manage Server required) to enable.`);
});

client.on(Events.MessageCreate, async (message) => {
  if (message.channel.id !== CHANNEL_ID) return;
  if (message.author.bot) return;

  const content = message.content.trim().toLowerCase();

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
    message.reply("Per-message nickname changing ACTIVATED (zesty list).").catch(() => {});
    return;
  }

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
    message.reply("Per-message nickname changing DISABLED.").catch(() => {});
    return;
  }

  if (!active) return;

  const member = message.member;
  if (!member) return;

  const me = message.guild.members.me;
  if (!me) return;
  if (!me.permissions.has(PermissionsBitField.Flags.ManageNicknames)) return;
  if (!(me.roles.highest.comparePositionTo(member.roles.highest) > 0)) return;

  const newNick = nextNickname(member.id);
  try {
    await member.setNickname(newNick, "Per-message nickname change (zesty list)");
  } catch {
    // Ignore errors (permissions / rate limit / hierarchy)
  }
});

client.login(DISCORD_TOKEN);

process.on("SIGTERM", () => {
  console.log("Shutting down...");
  client.destroy();
  process.exit(0);
});
