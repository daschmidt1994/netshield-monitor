# REST API

Interactive OpenAPI docs: `https://<your-instance>/api/docs` (schema at `/api/openapi.json`).

Authentication: `Authorization: Bearer nsm_…` (API token) or the web session cookie (+ `X-CSRF-Token` header for
non-GET requests). All endpoints except `/api/v1/health` require authentication.

Time range parameters (all statistics endpoints): `range=live|1h|24h|7d|30d` **or** `from=<epoch>&to=<epoch>`
(max 366 days). Optional `host=<domain>` filter.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | liveness (`status`, `version`, `time`) – public |
| GET | `/api/v1/sources` | collector status, privacy settings |
| GET | `/api/v1/overview` | dashboard KPIs |
| GET | `/api/v1/timeseries` | requests per bucket and category (`bucket` seconds optional) |
| GET | `/api/v1/countries` | requests / allowed / blocked per country |
| GET | `/api/v1/statuses` | HTTP status code distribution |
| GET | `/api/v1/top/paths` | top URLs (`category`, `limit`) – raw retention only |
| GET | `/api/v1/top/sources` | top (truncated) source networks |
| GET | `/api/v1/requests` | recent requests (`host`, `category`, `status`, `before`, `limit`) |
| GET | `/api/v1/domains` | domains with stats (`include_hidden`) |
| GET | `/api/v1/domains/{host}` | domain detail (all of the above for one domain) |
| POST | `/api/v1/domains` | add manual domain *(admin)* |
| PATCH | `/api/v1/domains/{host}` | rename / hide *(admin)* |
| DELETE | `/api/v1/domains/{host}` | delete manual/removed domain *(admin)* |
| GET | `/api/v1/crowdsec/summary` | alerts, decisions, enforcement per layer |
| GET | `/api/v1/crowdsec/alerts` | alert list (`severity`, `scenario`, `before_id`, `limit`) |
| GET | `/api/v1/crowdsec/decisions` | active local decisions + totals |
| GET | `/api/v1/crowdsec/metrics` | latest sampled CrowdSec metrics |
| GET | `/api/v1/notifications` | notifications (`after_id` for polling) |
| GET | `/api/v1/ha/summary` | compact snapshot for Home Assistant |
| GET | `/api/v1/stream` | Server-Sent Events: `update`, `notification` |
| POST | `/api/v1/auth/login` · `/auth/logout` · GET `/auth/me` | web session |
| GET/POST/DELETE | `/api/v1/admin/tokens` | API tokens *(admin)* |
| GET/PUT | `/api/v1/admin/settings` | notification thresholds *(admin)* |
| POST | `/api/v1/admin/notifications/test` | send a test message via ntfy *(admin)* |

Errors: JSON `{"detail": "…"}` with 401/403/404/409/422/429. Rate limit: `NETSHIELD_RATE_LIMIT_PER_MINUTE` per client.

Example:

```bash
curl -H "Authorization: Bearer $TOKEN" "https://netshield.example.com/api/v1/overview?range=24h"
```
