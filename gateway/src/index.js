import express from "express";
import pino from "pino";

import {
  QR_TTL_SECONDS,
  createSession,
  disconnectSession,
  getSession,
  logoutSession,
  restoreAll,
  restoreSession,
  sendMessage,
} from "./session-manager.js";

const log = pino({ name: "gateway" });

const PORT = Number(process.env.PORT || 4000);
const TOKEN = process.env.SERVICE_TOKEN || "";

const app = express();
app.use(express.json({ limit: "1mb" }));

// Bearer-token auth on everything except /health — service-to-service only.
app.use((req, res, next) => {
  if (req.path === "/health") return next();
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!TOKEN || token !== TOKEN) {
    return res.status(401).json({ error: "unauthorized" });
  }
  return next();
});

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.post("/sessions", async (req, res) => {
  const { bot_id } = req.body || {};
  if (!bot_id) return res.status(400).json({ error: "bot_id is required" });
  try {
    const sess = await createSession(String(bot_id));
    return res.status(201).json({ session_id: sess.id, state: sess.state });
  } catch (err) {
    log.error({ err: String(err) }, "create session failed");
    return res.status(500).json({ error: "failed to create session" });
  }
});

app.get("/sessions/:id", (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  return res.json({
    session_id: sess.id,
    state: sess.state,
    phone_number: sess.phoneNumber,
    has_qr: Boolean(sess.qr),
  });
});

app.get("/sessions/:id/qr", (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  if (!sess.qr) {
    return res.status(409).json({
      error: "no QR available",
      state: sess.state,
    });
  }
  return res.json({ qr: sess.qr, ttl: QR_TTL_SECONDS });
});

app.get("/sessions/:id/status", (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  return res.json({ state: sess.state, phone_number: sess.phoneNumber });
});

app.post("/sessions/:id/disconnect", async (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  await disconnectSession(sess);
  return res.json({ state: sess.state });
});

app.post("/sessions/:id/restore", async (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  try {
    await restoreSession(sess);
    return res.json({ state: sess.state, phone_number: sess.phoneNumber });
  } catch (err) {
    return res.status(409).json({ error: String(err.message || err) });
  }
});

app.delete("/sessions/:id", async (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  await logoutSession(sess);
  return res.json({ state: "logged_out" });
});

app.post("/sessions/:id/messages", async (req, res) => {
  const sess = getSession(req.params.id);
  if (!sess) return res.status(404).json({ error: "session not found" });
  const { to, type, text, media_url, caption } = req.body || {};
  if (!to) return res.status(400).json({ error: "to is required" });
  try {
    const result = await sendMessage(sess, { to, type, text, media_url, caption });
    return res.json(result);
  } catch (err) {
    const status = err.status || 500;
    return res.status(status).json({ error: String(err.message || err) });
  }
});

app.listen(PORT, async () => {
  log.info({ port: PORT }, "fomobot gateway listening");
  try {
    await restoreAll();
  } catch (err) {
    log.error({ err: String(err) }, "session restore sweep failed");
  }
});
