# Architecture overview

## Tenancy

```
User ─┬─< OrganizationMembership(role, status) >─┬─ Organization ── Plan
      └──────────────────────────────────────────┘
Organization ─< Bot ─1:1─ WhatsAppSession (encrypted creds)
Bot ─< Conversation >─ Contact
Conversation ─< Message
Organization ─< APIKey / Webhook / Automation / Template / Event / ApiRequestLog
```

Every org-owned queryset is filtered in `TenantViewSet.filter_queryset`
(`tenant_field`, default `organization`) — this hook runs for both list and
object lookups, so overriding `get_queryset` in a viewset can't bypass it.
Object-level `SameOrganizationObject` double-checks on detail routes.

Tenant context resolution (`common.tenant`):

- API-key request → `key.organization`.
- JWT/session → `X-Organization-ID` verified against active memberships
  (falls back to first membership).

## WhatsApp provider seam

`apps/whatsapp/providers/base.py` defines the contract:
`start_session / get_qr / get_status / disconnect / logout /
restore_session / send_message / heartbeat / get_contacts / handle_event`.

Implementations: `mock` (dev/test — in-memory pairing via DB metadata),
`external` (HTTP gateway). Selected by `WHATSAPP_PROVIDER`; register custom
providers via `apps.whatsapp.providers.register("name", "dotted.path")`.

## Session lifecycle

`created → connecting → qr_required → connected`, with `reconnecting`,
`disconnected`, `logged_out`, `error`. Sessions persist in the DB
(credentials Fernet-encrypted), so `restore_sessions_on_boot` rebuilds provider
connections after restarts. QR codes expire (`QR_TTL_SECONDS`) and regeneration
is rate-limited per bot per hour.

## Event flow

```
provider ingress (POST /api/v1/whatsapp/ingress/)
  → ProviderEvent (dedupe by provider_event_id)
  → handle_provider_event → MessageService.ingest_inbound / session transitions
  → emit(Event) → Celery fan-out:
      dispatch_event_to_webhooks   (HMAC-signed deliveries + retries)
      dispatch_event_to_automations (trigger → conditions → actions)
      push_event_to_inbox          (Channels group org_<id>_inbox)
```

Outbound: `POST /messages/send/` → validate + `queued` (+ idempotency key)
→ `process_outbound_message` worker → provider → `sent` + status updates via
provider events.

## Plans & billing (free today)

`PlanService` is the only place limits are read (`max_bots`, `messages_per_day`,
`api_requests_per_minute`, `max_webhooks`, `max_automation_rules`,
`max_contacts`, `log_retention_days`). `Subscription`, `UsageRecord`, `Invoice`
are ready for a payment provider without touching core flows.
