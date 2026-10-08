import { randomUUID } from "node:crypto";

import pino from "pino";

const log = pino({ name: "events" });

const CALLBACK_URL = process.env.CALLBACK_URL || "http://web:8000";
const TOKEN = process.env.SERVICE_TOKEN || "";
const INGRESS_PATH = "/api/v1/whatsapp/ingress/";

const MAX_ATTEMPTS = 5;

/**
 * POST a provider event to the Django ingress endpoint.
 * Retries with exponential backoff — the Django side deduplicates on `id`,
 * so re-delivery is safe.
 */
export async function emitEvent(session, type, data = {}) {
  const payload = {
    id: randomUUID(),
    type,
    provider_session_id: session.id,
    bot_id: session.botId,
    data,
  };

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    try {
      const resp = await fetch(`${CALLBACK_URL}${INGRESS_PATH}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-FomoBot-Provider-Token": TOKEN,
        },
        body: JSON.stringify(payload),
      });
      if (resp.ok) return;
      log.warn({ type, attempt, status: resp.status }, "ingress rejected event");
      if (resp.status >= 400 && resp.status < 500) return; // permanent — don't retry
    } catch (err) {
      log.warn({ type, attempt, err: String(err) }, "ingress unreachable");
    }
    await sleep(Math.min(1000 * 2 ** (attempt - 1), 15000));
  }
  log.error({ type, session: session.id }, "event dropped after retries");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
