# Running NetShield at home (e.g. Unraid) and reaching NetBird/CrowdSec via NetBird

NetShield does not have to run on the NetBird/CrowdSec server. A typical setup:

```
 Home server (Unraid)                              VPS (NetBird + CrowdSec)
 ┌─────────────────────────────┐                   ┌──────────────────────────────────────┐
 │ netshield-monitor ─────────────── HTTPS ───────▶│ NetBird management API (public URL)  │
 │        │                    │                   │                                      │
 │        └── NetBird tunnel (WireGuard) ─────────▶│ crowdsec-lapi-bridge :18080 (NetBird │
 │ PostgreSQL                  │                   │   IP only) ──▶ 127.0.0.1:8080 LAPI   │
 └─────────────────────────────┘                   └──────────────────────────────────────┘
```

| Data source | How it is reached | Change on the VPS |
|---|---|---|
| NetBird access logs + services | public management URL with the PAT | none |
| CrowdSec decisions + alerts | NetBird tunnel → LAPI bridge | small bridge container (below) |
| CrowdSec metrics (optional) | NetBird tunnel → metrics bridge `:18081` | `docker-compose.metrics.yml` (below) |
| ntfy | public ntfy URL | none |

Advantages: NetShield keeps working (and alerts you) when the VPS is down, data stays at home, the VPS saves RAM.
Trade-off: CrowdSec data needs the tunnel. NetBird logs missed while the VPS/API is unreachable are fetched later
(NetBird keeps them for 7 days).

---

## Part 1 – on the VPS: CrowdSec LAPI bridge

The LAPI only listens on `127.0.0.1:8080`. The bridge forwards **only the NetBird IP** of the VPS to it.
The CrowdSec container is **not** changed; if NetBird is not up yet at boot, only the bridge retries.

```bash
# as root on the VPS
mkdir -p /opt/stacks/crowdsec-bridge && cd /opt/stacks/crowdsec-bridge
curl -fsSLO https://raw.githubusercontent.com/daschmidt1994/netshield-monitor/main/docker/crowdsec-bridge/docker-compose.yml
curl -fsSL  https://raw.githubusercontent.com/daschmidt1994/netshield-monitor/main/docker/crowdsec-bridge/.env.example -o .env
sed -i "s/^NETBIRD_IP=.*/NETBIRD_IP=$(netbird status | sed -n 's#^NetBird IP: *\([0-9.]*\)/.*#\1#p')/" .env
cat .env
docker compose up -d
docker logs crowdsec-lapi-bridge
ss -tlnp | grep 18080          # must show <NetBird IP>:18080, NOT 0.0.0.0
```

### Optional: CrowdSec metrics

CrowdSec's Prometheus endpoint (`:6060`) is only reachable inside its Docker network. To show parser/scenario/bouncer
metrics remotely, start the metrics override as well:

```bash
curl -fsSLO https://raw.githubusercontent.com/daschmidt1994/netshield-monitor/main/docker/crowdsec-bridge/docker-compose.metrics.yml
docker compose -f docker-compose.yml -f docker-compose.metrics.yml up -d
ss -tlnp | grep 18081          # must show <NetBird IP>:18081
```

Then set `NETSHIELD_CROWDSEC_METRICS_URL=http://<NetBird IP of the VPS>:18081/metrics` and allow TCP 18081 in the
NetBird policy below.

### NetBird access policy (important)

NetBird dashboard → **Access Control → Policies → Add policy**

- Source: a group containing only the home server peer (e.g. `netshield`)
- Destination: the VPS peer's group
- Protocol **TCP**, port **18080**, direction one-way

If your account still has the default *All → All* policy, every peer can reach the port; the LAPI still requires the
bouncer key / machine password, but restricting it is strongly recommended.

### Credentials

Reuse the existing `netshield-monitor` bouncer key and machine (see [installation.md](installation.md#3-crowdsec-bouncer-key--machine)).
They are not bound to an IP.

---

## Part 2 – PostgreSQL on the home server

In your PostgreSQL container (Unraid: *Docker → postgres → Console*):

```bash
psql -U postgres -c "CREATE USER netshield PASSWORD '<strong password>';"
psql -U postgres -c "CREATE DATABASE netshield OWNER netshield;"
```

NetShield creates its tables on first start. Disk usage at ~35 000 requests/day: roughly 0.5–1 GB for 14 days of
raw requests plus a few MB per month of aggregates.

---

## Part 3 – NetShield on the home server (Unraid)

Requirements on Unraid: the **Docker Compose Manager** plugin (Community Applications) and the Unraid host being a
**NetBird peer** (NetBird plugin/container with host networking), so containers can reach `100.x.y.z` addresses.

```bash
# Unraid terminal
mkdir -p /mnt/user/appdata/netshield && cd /mnt/user/appdata/netshield
# Unraid has no git by default – download the release archive instead
curl -fsSL https://github.com/daschmidt1994/netshield-monitor/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
cp .env.example .env
mkdir -p secrets && chmod 700 secrets
```

`.env` (only the lines that differ from the defaults):

```bash
NETSHIELD_TIMEZONE=Europe/Vienna
NETSHIELD_BIND=0.0.0.0                 # or the Unraid LAN IP
NETSHIELD_PORT=8090
NETSHIELD_NETBIRD_URL=https://netbird.example.com
NETSHIELD_CROWDSEC_LAPI_URL=http://<NetBird IP of the VPS>:18080
NETSHIELD_CROWDSEC_METRICS_URL=        # optional: http://<NetBird IP of the VPS>:18081/metrics
NETSHIELD_COOKIE_SECURE=false          # true once the UI is served via HTTPS (NetBird service)
NETSHIELD_NTFY_URL=https://ntfy.example.com
NETSHIELD_NTFY_TOPIC=netshield-<random>
```

Secrets (one value per file, no quotes):

```bash
printf '%s' 'postgresql+asyncpg://netshield:<password>@<Unraid LAN IP>:5432/netshield' > secrets/database_url
printf '%s' 'nbp_…'  > secrets/netbird_token
printf '%s' '…'      > secrets/crowdsec_bouncer_key
printf '%s' '…'      > secrets/crowdsec_machine_password
touch secrets/ntfy_token                 # empty = public topic
chmod 644 secrets/*                      # container user uid 10001 must read them
```

> Use the LAN IP (or the PostgreSQL container name if both containers share a custom Docker network) – not
> `localhost`, which inside the container is the container itself.

Start (Compose Manager: *Add new stack* → point it at `/mnt/user/appdata/netshield`, or in the terminal):

```bash
docker compose up -d
docker compose exec netshield netshield check
docker compose exec netshield netshield create-admin
```

Expected `check` output:

```
[ OK ] NetBird access logs: … access log entries in the last hour
[ OK ] NetBird services: … services
[ OK ] CrowdSec decisions (bouncer key): … local decisions
[ OK ] CrowdSec alerts (machine login): … alerts in the last hour
```

The UI is at `http://<Unraid IP>:8090`. For access from outside home, create a NetBird reverse-proxy service pointing
to the Unraid peer, port 8090 (ideally *NetBird-only*), then set `NETSHIELD_COOKIE_SECURE=true` and restart.

### Troubleshooting

| Symptom | Check |
|---|---|
| `CrowdSec LAPI not reachable` | from Unraid: `curl -s -o /dev/null -w '%{http_code}' http://<VPS NetBird IP>:18080/v1/decisions` → `403` = reachable (no key sent). Timeout → NetBird policy or bridge not running |
| `bind … failed` in bridge logs | NetBird on the VPS not up or wrong `NETBIRD_IP` |
| database errors on start | URL in `secrets/database_url`, PostgreSQL reachable from the container, user owns the database |
| NetBird `401` | token expired/revoked → new PAT into `secrets/netbird_token`, `docker compose restart` |
