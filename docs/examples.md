# Examples

## cURL

```bash
# create bot
curl -X POST $BASE/api/v1/bots/ -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"name":"Support Bot"}'

# send message (idempotent)
curl -X POST $BASE/api/v1/messages/send/ \
  -H "X-API-Key: $KEY" -H "Idempotency-Key: order-1234" \
  -d '{"bot_id":"bot_...","to":"2557XXXXXXXX","type":"text","text":"Your order shipped!"}'
```

## Python

```python
import requests

API = "https://api.fomobot.example/api/v1"
KEY = "fb_live_..."
H = {"X-API-Key": KEY}

bot = requests.post(f"{API}/bots/", headers=H,
                    json={"name": "Sales"}).json()["data"]

r = requests.post(
    f"{API}/messages/send/",
    headers={**H, "Idempotency-Key": "ord-42"},
    json={"bot_id": bot["id"], "to": "2557XXXXXXXX",
          "type": "text", "text": "Hello!"},
)
print(r.json()["data"]["message_id"], r.json()["data"]["status"])
```

## JavaScript

```js
const API = "https://api.fomobot.example/api/v1";
const res = await fetch(`${API}/messages/send/`, {
  method: "POST",
  headers: {"X-API-Key": KEY, "Idempotency-Key": crypto.randomUUID(),
            "Content-Type": "application/json"},
  body: JSON.stringify({bot_id: "bot_...", to: "2557XXXXXXXX",
                        type: "text", text: "Hello"}),
});
const {data} = await res.json(); // {message_id, status: "queued"}
```

## PHP

```php
$ch = curl_init("https://api.fomobot.example/api/v1/messages/send/");
curl_setopt_array($ch, [
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_POST => true,
  CURLOPT_HTTPHEADER => ["X-API-Key: $KEY", "Content-Type: application/json"],
  CURLOPT_POSTFIELDS => json_encode([
    "bot_id" => "bot_...", "to" => "2557XXXXXXXX",
    "type" => "text", "text" => "Hello",
  ]),
]);
$resp = json_decode(curl_exec($ch), true);
echo $resp["data"]["message_id"];
```

## Verify a webhook signature (Node)

```js
const crypto = require("crypto");
const sig = crypto.createHmac("sha256", process.env.WEBHOOK_SECRET)
  .update(`${req.headers["x-fomobot-timestamp"]}.${rawBody}`)
  .digest("hex");
const ok = crypto.timingSafeEqual(
  Buffer.from(`sha256=${sig}`),
  Buffer.from(req.headers["x-fomobot-signature"]));
```
