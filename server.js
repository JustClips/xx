import "dotenv/config";
import {
  Client,
  GatewayIntentBits,
  Partials,
  Events,
  PermissionsBitField
} from "discord.js";

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;

// Hard-coded channel ID (no env var needed for it)
const CHANNEL_ID = "1410395105965375600";

if (!DISCORD_TOKEN) {
  console.error("Missing DISCORD_TOKEN environment variable.");
  process.exit(1);
}

// Bot active flag toggled by !start / !stop inside the target channel
let active = false;

// Track last nickname per user (to reduce immediate duplicates)
const lastNick = new Map();

// Word lists for nickname generation
const ADJECTIVES = [
  "Zesty","Fuzzy","Icy","Brave","Cosmic","Witty","Quirky","Spicy","Mellow","Silly",
  "Bouncy","Glitchy","Nebula","Rusty","Swift","Snazzy","Giddy","Chill","Dizzy","Soggy"
];
const NOUNS = [
  "Llama","Otter","Falcon","Badger","Kraken","Panda","Mantis","Cobra","Pixel","Comet",
  "Raptor","Golem","Lynx","Phoenix","Dragon","Puffin","Beetle","Fox","Aardvark","Moose"
];

function generateNickname(userId) {
  for (let i = 0; i < 5; i++) {
    const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
    const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)];
    const num = Math.floor(100 + Math.random() * 900);
    const nick = `${adj}${noun}${num}`;
    if (lastNick.get(userId) !== nick) {
      lastNick.set(userId, nick);
      return nick;
    }
  }
  const fallback = `Nick${Math.floor(Math.random() * 100000)}`;
  lastNick.set(userId, fallback);
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
  console.log(`Target channel: ${CHANNEL_ID}`);
  console.log("Type !start in that channel (Manage Server permission required) to activate.");
});

client.on(Events.MessageCreate, async (message) => {
  // Commands and nickname changes only in the specified channel
  if (message.channel.id !== CHANNEL_ID) return;
  if (message.author.bot) return;

  const content = message.content.trim().toLowerCase();

  // Handle !start command
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
    message.reply("Per-message nickname changing ACTIVATED.").catch(() => {});
    return;
  }

  // Handle !stop command
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

  // Change this author's nickname every message while active
  const member = message.member;
  if (!member) return;

  const me = message.guild.members.me;
  if (!me) return;
  if (!me.permissions.has(PermissionsBitField.Flags.ManageNicknames)) return;
  if (!(me.roles.highest.comparePositionTo(member.roles.highest) > 0)) return; // role hierarchy check

  const newNick = generateNickname(member.id);
  try {
    await member.setNickname(newNick, "Per-message nickname change");
  } catch (err) {
    // Ignore (no permission / rate limit / hierarchy)
  }
});

client.login(DISCORD_TOKEN);

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("Shutting down...");
  client.destroy();
  process.exit(0);
});
