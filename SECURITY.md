# Security Policy / Sicherheitsrichtlinie

## Reporting a vulnerability

Please **do not** open a public issue for security problems.
Use GitHub's private vulnerability reporting:
<https://github.com/daschmidt1994/netshield-monitor/security/advisories/new>

You can expect an initial response within 7 days.

## Supported versions

Only the latest release receives security fixes.

## Security principles of this project

- No credentials, real domains or real IP addresses in the repository.
- External systems (NetBird, CrowdSec) are accessed with the least privileges available.
  Where an upstream API offers no read-only role, this is documented in `docs/`.
- NetBird/CrowdSec credentials are never exposed through the public app API.
- `X-Forwarded-For` is only honoured from explicitly configured trusted proxies.
- IP addresses are personal data (GDPR). They are truncated by default and raw
  data is deleted after a configurable retention period.

---

## Sicherheitslücke melden

Bitte **keine** öffentlichen Issues für Sicherheitsprobleme eröffnen, sondern
die private Meldefunktion von GitHub verwenden (Link oben). Eine erste Antwort
erfolgt innerhalb von 7 Tagen.
