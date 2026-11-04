# Installation / Erstkonfiguration

This guide assumes the common setup: NetBird (self-hosted, combined server) and CrowdSec run as Docker
containers on the same host, and NetShield Monitor is added next to them.
*Die Anleitung ist auf Englisch; alle Befehle sind identisch.*

## 0. Requirements

| Component | Minimum | Verified |
|---|---|---|
| NetBird management + reverse proxy | v0.65 (proxy access logs), v0.69 (CrowdSec verdicts) | v0.81.3 |
| CrowdSec | v1.6 | v1.8.1 |
| Docker / Compose | Compose v2 | 29.x |

## 1. Clone and prepare

```bash
git clone https://github.com/daschmidt1994/netshield-monitor.git
cd netshield-monitor
cp .env.example .env
mkdir -p secrets && chmod 700 secrets
```

Edit `.env`:

- `NETSHIELD_NETBIRD_URL` – your NetBird management/dashboard URL, e.g. `https://netbird.example.com`
- `NETSHIELD_EXTERNAL_NETWORK` – the Docker network of your NetBird/CrowdSec stack (`docker network ls`; the
  official combined setup uses `netbird_netbird`). NetShield joins it to reach `crowdsec:8080` and `crowdsec:6060`.
- `NETSHIELD_TIMEZONE` – used for "today" and daily visitor counts.

## 2. NetBird: service user + personal access token

1. NetBird dashboard → **Team → Service Users → Create Service User**, name `netshield-monitor`.
   Pick the role with the fewest permissions available that can read *Activity → Proxy Events* and the
   reverse-proxy services (role **User** worked in v0.81; use a read-only/auditor role if your version offers one).
2. Open the service user → **Create Token** → copy it (shown once).
3. Store it **as a file** (never in `.env`, never in Git):

```bash
printf '%s' 'nbp_…' > secrets/netbird_token
```

NetShield uses only `GET /api/events/proxy` and `GET /api/reverse-proxies/services`.

> NetBird keeps proxy access logs for 7 days by default. NetShield copies them into its own database on
> first start (backfill, oldest first – takes a few minutes for ~250 k requests) and then polls every 30 s.

## 3. CrowdSec: bouncer key + machine

```bash
# read access to active decisions
docker exec <crowdsec-container> cscli bouncers add netshield-monitor -o raw > secrets/crowdsec_bouncer_key

# alerts need a machine (watcher) login. Write the credentials to stdout – NEVER use --force here:
# that would overwrite CrowdSec's own local_api_credentials.yaml.
docker exec <crowdsec-container> cscli machines add netshield-monitor --auto -f - 2>&1 \
  | sed -n 's/^password: *//p' > secrets/crowdsec_machine_password
```

⚠️ CrowdSec has **no read-only machine role**. The machine could in theory push alerts. NetShield only reads,
keeps the credentials server-side and never exposes them through its API; keep the LAPI on an internal network.

Metrics: NetShield reads `http://crowdsec:6060/metrics` (enabled by default in the CrowdSec container).
It is used for decision totals (community blocklists can hold > 30 000 entries) and AppSec counters.

## 4. ntfy (optional)

```bash
# .env
NETSHIELD_NTFY_URL=https://ntfy.example.com
NETSHIELD_NTFY_TOPIC=netshield-<random>
# access token if the topic is protected (empty file = no token)
printf '%s' 'tk_…' > secrets/ntfy_token
```

Subscribe to the topic in the ntfy Android app for instant push notifications. Use the **Test ntfy** button in the
web UI (Settings) to verify.

## 5. Start

```bash
touch secrets/ntfy_token                 # must exist, may be empty
chmod 644 secrets/*                      # container runs as uid 10001 and must read them;
                                         # the secrets/ directory itself stays 700 for other host users
docker compose up -d
docker compose exec netshield netshield create-admin
docker compose exec netshield netshield check
```

`netshield check` prints one line per data source, e.g.

```
[ OK ] NetBird access logs: 1906 access log entries in the last hour
[ OK ] NetBird services: 18 services
[ OK ] CrowdSec decisions (bouncer key): 12 local decisions
[ OK ] CrowdSec alerts (machine login): 3 alerts in the last hour
[ OK ] CrowdSec metrics: 720 metric lines
```

Missing sources are skipped – NetShield works with any subset (e.g. NetBird only).

## 6. Access the web UI

The container port is bound to `127.0.0.1:8090` only. Recommended ways to reach it:

**A) NetBird reverse proxy service (recommended).** In the NetBird dashboard create a reverse proxy service
`netshield.example.com` → target: the host peer, port `8090`. Enable *NetBird-only* (private) access if your
version supports it, so only your own devices can open it. Then set in `.env`:

```bash
NETSHIELD_COOKIE_SECURE=true
NETSHIELD_TRUSTED_PROXIES=172.30.0.2/32   # IP of the netbird-proxy container (docker inspect)
```

`NETSHIELD_TRUSTED_PROXIES` is only used for rate limiting/login throttling. `X-Forwarded-For` from any other
source is ignored.

**B) SSH tunnel** for quick tests: `ssh -L 8090:127.0.0.1:8090 your-server` → `http://127.0.0.1:8090`
(set `NETSHIELD_COOKIE_SECURE=false` for plain http).

## 7. Tokens for Android and Home Assistant

Web UI → **Settings → API tokens → Create** (scope `read`). The token is shown once. Use one token per device so
you can revoke them individually. CLI alternative: `docker compose exec netshield netshield create-token android`.

## Updating

```bash
git pull && docker compose up -d --build     # or: docker compose pull && docker compose up -d
```

The SQLite database lives in the `netshield_data` volume and survives restarts and updates.

## PostgreSQL (optional)

For larger installations see [`examples/docker-compose.postgres.yml`](../examples/docker-compose.postgres.yml) and set
`NETSHIELD_DATABASE_URL=postgresql+asyncpg://…`.
