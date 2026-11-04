# Privacy / Datenschutz (GDPR / DSGVO)

IP addresses can be personal data (CJEU C‑582/14 *Breyer*). NetShield is built to process as little as possible:

| Measure | Default |
|---|---|
| IP truncation before storage | IPv4 `/24`, IPv6 `/48` (`NETSHIELD_IP_MODE=truncate`) |
| Visitor counting | daily-salted HMAC pseudonym, salt deleted after the day → unlinkable |
| Raw request retention | 14 days (`NETSHIELD_RAW_RETENTION_DAYS`) |
| Aggregates (no IPs) | 365 days |
| CrowdSec alerts | 90 days, source truncated |
| Community blocklist decisions | only counts are stored, not the IPs |
| Backups (Android) | disabled; token encrypted with Android Keystore |
| Logs | no request URLs, IPs or secrets in application logs |
| External calls | only your NetBird, CrowdSec and (optional) ntfy instance – no telemetry, no CDNs, map data bundled |

Notes for operators:

- NetBird itself stores full IPs in its access log (7 days by default) – adjust `accessLogRetentionDays` if needed.
- `NETSHIELD_IP_MODE=full` stores complete addresses (e.g. to copy IPs for blocklists). Document a legal basis
  (typically legitimate interest in IT security, Art. 6(1)(f) GDPR) and keep the retention short.
- GeoIP locations are approximate and must not be treated as a person's location.
