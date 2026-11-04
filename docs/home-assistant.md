# Home Assistant integration

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → `https://github.com/daschmidt1994/netshield-monitor`, category **Integration**.
2. Install **NetShield Monitor**, restart Home Assistant.
3. **Settings → Devices & services → Add integration → NetShield Monitor**.
4. Enter the backend URL (e.g. `https://netshield.example.com`) and an API token with scope `read`
   (NetShield web UI → Settings → API tokens).

Manual install: copy `custom_components/netshield_monitor` into `<config>/custom_components/`.

Options (⚙ on the integration): update interval (30–3600 s, default 60) and per-domain sensors on/off.

## Entities

| Entity | Meaning |
|---|---|
| `sensor.netshield_requests_today` | requests since local midnight |
| `sensor.netshield_requests_24h` | requests in the last 24 h |
| `sensor.netshield_requests_per_minute` | average over the last 5 min |
| `sensor.netshield_visitors_today` | estimated unique visitors today |
| `sensor.netshield_blocked_requests` | requests rejected by CrowdSec in the NetBird proxy (24 h) |
| `sensor.netshield_crowdsec_active_decisions` | active **local** decisions (attribute: community blocklist size) |
| `sensor.netshield_crowdsec_alerts_24h` | CrowdSec alerts (attribute `critical`) |
| `sensor.netshield_top_country` | most frequent country (24 h, approximate GeoIP) |
| `sensor.netshield_active_domains` | domains with traffic in 24 h |
| `sensor.netshield_security_status` | `ok` / `warning` / `critical` |
| `sensor.netshield_last_notification` | latest notification (diagnostic) |
| `sensor.netshield_domain_<domain>` | requests 24 h per domain (attributes: blocked, req/min, CrowdSec mode) |
| `binary_sensor.netshield_backend_online` | backend reachable |
| `binary_sensor.netshield_security_alert` | security status is `critical` |
| `binary_sensor.netshield_source_problem` | a data source reports errors |

No entities are created per IP address or per request.

## Events

| Event | When |
|---|---|
| `netshield_monitor_notification` | every new NetShield notification (`kind`, `severity`, `title`, `message`, `host`) |
| `netshield_monitor_security_alert` | new notification with severity `critical` |

History is not replayed after a restart.

## Examples

- Automations: [`examples/home-assistant-automations.yaml`](../examples/home-assistant-automations.yaml)
- Dashboard: [`examples/lovelace-dashboard.yaml`](../examples/lovelace-dashboard.yaml) (only built-in cards).
  Add it via *Settings → Dashboards → Add dashboard → ⋮ → Raw configuration editor*.

## Diagnostics

*Download diagnostics* redacts URL, token, domain names and messages.
