import fs from "node:fs";
import path from "node:path";

import { Boom } from "@hapi/boom";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import pino from "pino";

import { emitEvent } from "./events.js";

const log = pino({ name: "sessions" });

const AUTH_DIR = process.env.AUTH_DIR || "/data/sessions";
// Baileys re-emits the pairing QR roughly every 20s; report a matching TTL
// so Django's cache never serves a code WhatsApp has already invalidated.
const QR_TTL_SECONDS = 20;

// FomoBot session states (must match apps.whatsapp.models.WhatsAppSession.State)
const State = {
  CONNECTING: "connecting",
  QR_REQUIRED: "qr_required",
  CONNECTED: "connected",
  RECONNECTING: "reconnecting",
  DISCONNECTED: "disconnected",
  LOGGED_OUT: "logged_out",
  ERROR: "error",
};

const sessions = new Map();

let cachedVersion;
async function baileysVersion() {
  if (!cachedVersion) {
    const { version } = await fetchLatestBaileysVersion();
    cachedVersion = version;
    log.info({ version: version.join(".") }, "baileys version");
  }
  return cachedVersion;
}

export function getSession(id) {
  return sessions.get(id);
}

export async function createSession(botId) {
  const id = `sess_${botId}`;
  if (sessions.has(id)) return sessions.get(id);
  const sess = {
    id,
    botId,
    sock: null,
    state: State.CONNECTING,
    qr: null,
    qrAt: 0,
    phoneNumber: "",
    intentional: false,
    authDir: path.join(AUTH_DIR, id),
    retries: 0,
  };
  sessions.set(id, sess);
  // Don't await socket init — dialing WhatsApp takes seconds and callers
  // poll /qr + /status anyway. Blocking here would hit HTTP timeouts.
  startSocket(sess).catch((err) => {
    sess.state = State.ERROR;
    log.error({ session: id, err: String(err) }, "socket start failed");
  });
  return sess;
}

async function startSocket(sess) {
  const version = await baileysVersion();
  fs.mkdirSync(sess.authDir, { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(sess.authDir);
  const logger = pino({ name: "baileys", level: "warn" });

  const sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    browser: ["FomoBot", "Chrome", "1.0.0"],
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  sess.sock = sock;
  sock.ev.on("creds.update", saveCreds);
  sock.ev.on("connection.update", (update) => onConnectionUpdate(sess, update));
  sock.ev.on("messages.upsert", (m) => onMessagesUpsert(sess, m));
  sock.ev.on("messages.update", (updates) => onMessagesUpdate(sess, updates));
}

async function onConnectionUpdate(sess, update) {
  const { connection, lastDisconnect, qr } = update;

  if (qr) {
    sess.qr = qr;
    sess.qrAt = Date.now();
    sess.state = State.QR_REQUIRED;
  }
  if (connection === "connecting") {
    sess.state = State.CONNECTING;
  }
  if (connection === "open") {
    sess.state = State.CONNECTED;
    sess.qr = null;
    sess.retries = 0;
    sess.phoneNumber = jidToNumber(sess.sock?.user?.id || "");
    log.info({ session: sess.id, phone: sess.phoneNumber }, "session connected");
    emitEvent(sess, "auth.authenticated", { phone_number: sess.phoneNumber });
  }
  if (connection === "close") {
    const statusCode = lastDisconnect?.error
      ? new Boom(lastDisconnect.error)?.output?.statusCode
      : 0;
    const loggedOut = statusCode === DisconnectReason.loggedOut;

    if (loggedOut || sess.state === State.LOGGED_OUT) {
      sess.state = State.LOGGED_OUT;
      sess.sock = null;
      cleanupAuth(sess);
      log.warn({ session: sess.id }, "logged out by WhatsApp");
      emitEvent(sess, "session.logged_out", {});
    } else if (sess.intentional) {
      sess.state = State.DISCONNECTED;
      sess.sock = null;
      emitEvent(sess, "session.disconnected", {});
    } else {
      // Transient drop — backoff and re-dial.
      sess.retries += 1;
      sess.state = State.RECONNECTING;
      const delay = Math.min(2000 * 2 ** Math.min(sess.retries, 5), 60000);
      log.info({ session: sess.id, retries: sess.retries, delay }, "reconnecting");
      setTimeout(() => startSocket(sess).catch((err) => {
        sess.state = State.ERROR;
        log.error({ session: sess.id, err: String(err) }, "reconnect failed");
      }), delay);
    }
  }
}

function onMessagesUpsert(sess, { messages }) {
  for (const msg of messages || []) {
    if (!msg?.message || msg.key?.fromMe) continue;
    const from = jidToNumber(msg.key.remoteJid);
    if (!from || from === "status") continue; // skip status broadcasts
    const type = detectType(msg.message);
    emitEvent(sess, "message.received", {
      provider_message_id: msg.key.id,
      from,
      type,
      text: extractText(msg.message),
      caption: extractCaption(msg.message),
      profile_name: msg.pushName || "",
      media_url: "",
      media_type: type === "text" ? "" : type,
      metadata: {
        has_media: type !== "text",
        is_group: String(msg.key.remoteJid || "").endsWith("@g.us"),
      },
    });
  }
}

function onMessagesUpdate(sess, updates) {
  // delivery receipts: 2=sent, 3=delivered, 4=read/played
  const STATUS_MAP = { 3: "message.delivered", 4: "message.read", 5: "message.read" };
  for (const u of updates || []) {
    const type = STATUS_MAP[u?.update?.status];
    if (!type || !u?.key?.id) continue;
    emitEvent(sess, type, { provider_message_id: u.key.id });
  }
}

export async function disconnectSession(sess) {
  sess.intentional = true;
  try {
    sess.sock?.end(undefined);
  } catch {
    /* socket may already be down */
  }
  if (sess.state !== State.LOGGED_OUT) sess.state = State.DISCONNECTED;
}

export async function logoutSession(sess) {
  sess.intentional = true;
  try {
    if (sess.sock) await sess.sock.logout();
  } catch {
    /* best-effort */
  }
  try {
    sess.sock?.end(undefined);
  } catch {
    /* noop */
  }
  sess.state = State.LOGGED_OUT;
  sess.sock = null;
  cleanupAuth(sess);
  sessions.delete(sess.id);
}

export async function restoreSession(sess) {
  if (!fs.existsSync(sess.authDir)) {
    throw new Error("No persisted credentials for this session");
  }
  sess.intentional = false;
  sess.state = State.CONNECTING;
  startSocket(sess).catch((err) => {
    sess.state = State.ERROR;
    log.error({ session: sess.id, err: String(err) }, "restore dial failed");
  });
}

export async function sendMessage(sess, { to, type, text, media_url, caption }) {
  if (!sess.sock || sess.state !== State.CONNECTED) {
    const err = new Error("Session is not connected");
    err.status = 409;
    throw err;
  }
  const jid = `${digitsOnly(to)}@s.whatsapp.net`;
  let content;
  if (type === "image") content = { image: { url: media_url }, caption: caption || "" };
  else if (type === "video") content = { video: { url: media_url }, caption: caption || "" };
  else if (type === "audio") content = { audio: { url: media_url }, mimetype: "audio/mpeg" };
  else if (type === "document") content = { document: { url: media_url }, caption: caption || "" };
  else content = { text: text || "" };

  const sent = await sess.sock.sendMessage(jid, content);
  return { message_id: sent?.key?.id || "", status: "sent" };
}

/** Reload persisted sessions on boot. */
export async function restoreAll() {
  if (!fs.existsSync(AUTH_DIR)) return;
  for (const dir of fs.readdirSync(AUTH_DIR)) {
    if (!dir.startsWith("sess_")) continue;
    if (!fs.existsSync(path.join(AUTH_DIR, dir, "creds.json"))) continue;
    const botId = dir.replace(/^sess_/, "");
    const sess = {
      id: dir,
      botId,
      sock: null,
      state: State.CONNECTING,
      qr: null,
      qrAt: 0,
      phoneNumber: "",
      intentional: false,
      authDir: path.join(AUTH_DIR, dir),
      retries: 0,
    };
    sessions.set(dir, sess);
    startSocket(sess).catch((err) => {
      sess.state = State.ERROR;
      log.error({ session: dir, err: String(err) }, "restore failed");
    });
    log.info({ session: dir }, "restoring persisted session");
  }
}

function cleanupAuth(sess) {
  fs.rmSync(sess.authDir, { recursive: true, force: true });
}

function jidToNumber(jid) {
  return String(jid || "").split("@")[0].split(":")[0];
}

function digitsOnly(phone) {
  return String(phone || "").replace(/\D/g, "");
}

function detectType(message) {
  if (message.imageMessage) return "image";
  if (message.videoMessage) return "video";
  if (message.audioMessage) return "audio";
  if (message.documentMessage) return "document";
  if (message.stickerMessage) return "sticker";
  if (message.locationMessage) return "location";
  if (message.contactMessage || message.contactsArrayMessage) return "contact";
  return "text";
}

function extractText(message) {
  return (
    message.conversation ||
    message.extendedTextMessage?.text ||
    extractCaption(message) ||
    ""
  );
}

function extractCaption(message) {
  return (
    message.imageMessage?.caption ||
    message.videoMessage?.caption ||
    message.documentMessage?.caption ||
    ""
  );
}

export { State, QR_TTL_SECONDS };
