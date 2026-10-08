/**
 * Terminal QR tool — creates/resumes a gateway session and renders the live
 * WhatsApp pairing QR in the terminal so it can be scanned directly.
 *
 *   node src/cli.js <bot_id>
 */
import qrcode from "qrcode-terminal";

const PORT = Number(process.env.PORT || 4000);
const TOKEN = process.env.SERVICE_TOKEN || "";
const BASE = `http://127.0.0.1:${PORT}`;

const botId = process.argv[2];
if (!botId) {
  console.error("Usage: node src/cli.js <bot_id>");
  process.exit(1);
}

const headers = {
  Authorization: `Bearer ${TOKEN}`,
  "Content-Type": "application/json",
};

async function api(method, path, body) {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await resp.json().catch(() => ({}));
  return { status: resp.status, data };
}

let lastQr = "";
let lastState = "";

console.log(`Creating session for bot ${botId}…`);
const created = await api("POST", "/sessions", { bot_id: botId });
if (created.status >= 400) {
  console.error("Failed:", created.data);
  process.exit(1);
}
const sessionId = created.data.session_id;
console.log(`Session: ${sessionId}`);
console.log("Scan the QR below with WhatsApp → Settings → Linked devices → Link a device\n");

const interval = setInterval(async () => {
  const { data: st } = await api("GET", `/sessions/${sessionId}/status`);

  if (st.state !== lastState) {
    lastState = st.state;
    console.log(`\n[state] ${st.state}${st.phone_number ? ` (${st.phone_number})` : ""}`);
  }

  if (st.state === "connected") {
    console.log("\nCONNECTED — WhatsApp linked successfully.");
    clearInterval(interval);
    process.exit(0);
  }

  const { data: qr } = await api("GET", `/sessions/${sessionId}/qr`);
  if (qr.qr && qr.qr !== lastQr) {
    lastQr = qr.qr;
    console.clear();
    console.log(`[${new Date().toLocaleTimeString()}] fresh QR — scan now:\n`);
    qrcode.generate(qr.qr, { small: true });
  }
}, 3000);
