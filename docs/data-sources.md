# Data sources and their limits

All integrations use documented interfaces only. Endpoints and field names were verified against the
NetBird v0.81.3 OpenAPI spec and a live NetBird 0.81.3 / CrowdSec 1.8.1 installation (Nov 2026).

## NetBird reverse proxy access logs – `GET /api/events/proxy`

Auth: `Authorization: Token <PAT>`. Pagination `page`/`page_size` (max 100), `sort_by=timestamp`,
`sort_order=asc`, `start_date` (RFC3339). NetShield polls with an inclusive start cursor and de-duplicates by id.

| Field | Used for |
|---|---|
| `timestamp`, `host`, `path`, `method`, `status_code`, `duration_ms`, `bytes_*` | request statistics |
| `source_ip` | visitors (pseudonymised), top sources (truncated), internal detection |
| `country_code`, `city_name` | GeoIP (NetBird ships its own GeoLite2 database) |
| `metadata.crowdsec_verdict` (`crowdsec_ban`/`crowdsec_captcha`), `auth_method_used` | **actual enforcement** |
| `metadata.crowdsec_mode = observe` | "would have been blocked" (request was let through) |

**Not available:** User-Agent, Referer, request headers. Bot/scanner detection is therefore heuristic
(path patterns such as `/.env`, `/wp-login.php`, `/.git/`, CrowdSec observe verdicts) and labelled "suspicious".

**Client IPs** are only correct when the proxy sees the real client: if something sits in front of NetBird
(Traefik with TLS passthrough, a load balancer), it must pass the address via PROXY protocol and be listed in
`trustedHTTPProxies`. The reference setup (Traefik TCP passthrough + PROXY v2) was verified to deliver real client IPs.
Requests originating on the host itself appear as the Docker gateway (e.g. `172.30.0.1`) and are classified **internal**.

**Retention:** NetBird deletes access logs after 7 days by default (`accessLogRetentionDays`). NetShield keeps its own copy.

## NetBird services – `GET /api/reverse-proxies/services`

Used for automatic domain discovery, enabled flag, `access_restrictions.crowdsec_mode` (enforce/observe) and
whether authentication is configured. Domains can additionally be added/hidden manually.

**Active connections:** no documented endpoint for live proxy connections was found; L4 entries appear in the
access log once a connection closes. NetShield therefore shows requests per minute instead of "active connections".

## CrowdSec LAPI

| Data | Endpoint | Credential |
|---|---|---|
| Active decisions (local origins) | `GET /v1/decisions?origins=crowdsec,cscli,…` | bouncer key (`X-Api-Key`) |
| Alerts | `POST /v1/watchers/login` → `GET /v1/alerts?since=…&until=…&include_capi=false` | machine id + password |
| Totals incl. community lists, AppSec | Prometheus `:6060/metrics` (`cs_active_decisions`, `cs_appsec_block_total`, …) | none (internal network) |

Notes:

- The LAPI rejects watcher logins whose `User-Agent` is not `<name>/<version>`; NetShield sends `netshield-monitor/<version>`.
- `/v1/alerts` returns at most `limit` entries; NetShield queries in time windows and splits windows that hit the limit.
- Bouncer usage metrics (`/v1/usage-metrics`) are *pushed* by bouncers and cannot be read back by third parties.
  The **firewall bouncer** drops packets before any HTTP request exists – NetShield shows it as "not measurable".

## Alert, decision, blocked – the three levels

| Level | Meaning | Source |
|---|---|---|
| Alert | a scenario fired (detection) | LAPI alerts |
| Decision | a remediation (ban/captcha) exists for an IP/range | LAPI decisions / metrics |
| Blocked | a request was **actually rejected** | NetBird access log (enforce mode) |

NetShield never reports "blocked" based on a decision alone.

### Alert severity

- **critical** – exploit-type scenario (`cve`, `vpatch`, `appsec`, brute force, …; configurable via
  `NETSHIELD_CRITICAL_SCENARIO_PATTERN`) **and** a decision was issued
- **high** – exploit-type scenario without decision (e.g. one request blocked by an AppSec virtual patch), or any scenario with a decision
- **low** – detection without remediation
