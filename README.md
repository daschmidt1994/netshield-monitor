# NetShield Monitor

**Self-hosted traffic & security monitor for the [NetBird](https://netbird.io) reverse proxy and [CrowdSec](https://crowdsec.net)** – with a web dashboard, a native Android app and a Home Assistant integration.

[🇩🇪 Deutsch](#deutsch) · [🇬🇧 English](#english)

---

## Deutsch

NetShield Monitor sammelt die **echten** Access-Logs deines NetBird-Reverse-Proxys und die Alerts/Entscheidungen deiner CrowdSec-Instanz und zeigt sie übersichtlich an:

- Requests, geschätzte Besucher, aktive Domains, Requests pro Minute
- Herkunftsländer (GeoIP von NetBird), interaktive Weltkarte
- HTTP-Statuscodes, Top-URLs, auffällige Requests (Scanner/Bots)
- CrowdSec: Alerts, Szenarien, aktive Entscheidungen (eigene vs. Community-Listen)
- **tatsächlich** vom NetBird-Proxy blockierte Requests (Ban/Captcha) – getrennt von Alerts und Entscheidungen
- Zeitverläufe für Live, 1 h, 24 h, 7 d, 30 d und frei wählbare Zeiträume
- Benachrichtigungen über **ntfy** (kritische Alerts, Angriffsspitzen, Domain-Ausfälle, Datenquellen-Fehler …)

Komponenten:

| Komponente | Technik | Ordner |
|---|---|---|
| Backend + Collector + Web-UI | Python 3.13, FastAPI, SQLAlchemy (SQLite/PostgreSQL), React + ECharts | `backend/`, `web/` |
| Android-App | Kotlin, Jetpack Compose, Material 3, Retrofit, Room | `android/` |
| Home-Assistant-Integration | Custom Integration (HACS), Config Flow, Coordinator | `custom_components/netshield_monitor/` |

### Schnellstart

```bash
git clone https://github.com/daschmidt1994/netshield-monitor.git
cd netshield-monitor
cp .env.example .env          # NETSHIELD_NETBIRD_URL usw. anpassen
mkdir -p secrets              # Zugangsdaten als Dateien ablegen (siehe docs/installation.md)
docker compose up -d          # auf dem NetBird-Host: -f docker-compose.yml -f docker-compose.netbird-host.yml
docker compose exec netshield netshield create-admin
docker compose exec netshield netshield check   # testet alle Datenquellen
```

Danach ist die Oberfläche unter `http://127.0.0.1:8090` erreichbar. Für den Zugriff von außen empfiehlt sich ein **NetBird-Reverse-Proxy-Service** (am besten *NetBird-only*). Vollständige Anleitung: **[docs/installation.md](docs/installation.md)**.

### Wichtige Hinweise

- **Keine erfundenen Werte:** Alles stammt aus NetBird- oder CrowdSec-Daten. Wo eine Quelle etwas nicht liefert (z. B. User-Agent, Firewall-Drops pro Request), zeigt NetShield „nicht messbar“ statt einer Schätzung.
- **Besucher sind geschätzt:** eindeutige, täglich neu pseudonymisierte IP-Adressen ohne Bots, blockierte und interne Zugriffe.
- **GeoIP ist ungefähr** und nicht zwingend der Standort einer Person.
- **Datenschutz:** IP-Adressen werden standardmäßig gekürzt (/24 bzw. /48) gespeichert, Rohdaten nach 14 Tagen gelöscht. Siehe [docs/privacy.md](docs/privacy.md).

### Dokumentation

[Installation](docs/installation.md) · [Betrieb zuhause/Unraid](docs/remote-setup.md) · [Architektur](docs/architecture.md) · [Datenquellen & Grenzen](docs/data-sources.md) · [API](docs/api.md) · [Home Assistant](docs/home-assistant.md) · [Android](docs/android.md) · [Datenschutz](docs/privacy.md) · [Tests](docs/testing.md) · [Screenshots](docs/screenshots.md)

---

## English

NetShield Monitor collects the **real** access logs of your NetBird reverse proxy and the alerts/decisions of your CrowdSec instance and presents them in a web UI, an Android app and Home Assistant:

- requests, estimated visitors, active domains, requests per minute
- countries of origin (GeoIP provided by NetBird) with an interactive world map
- HTTP status codes, top URLs, suspicious requests (scanners/bots)
- CrowdSec alerts, scenarios, active decisions (local vs. community blocklists)
- requests **actually** blocked by the NetBird proxy (ban/captcha) – kept separate from alerts and decisions
- time ranges: live, 1 h, 24 h, 7 d, 30 d, custom
- notifications via **ntfy** (critical alerts, attack spikes, domain outages, data source failures …)

### Quick start

```bash
git clone https://github.com/daschmidt1994/netshield-monitor.git
cd netshield-monitor
cp .env.example .env          # adjust NETSHIELD_NETBIRD_URL etc.
mkdir -p secrets              # put credentials into files (see docs/installation.md)
docker compose up -d          # on the NetBird host: -f docker-compose.yml -f docker-compose.netbird-host.yml
docker compose exec netshield netshield create-admin
docker compose exec netshield netshield check   # verifies all data sources
```

The UI is then available at `http://127.0.0.1:8090`. Publish it through a NetBird reverse proxy service (ideally *NetBird-only*) instead of opening a port. Full guide: **[docs/installation.md](docs/installation.md)** · running on another machine (home server/Unraid): **[docs/remote-setup.md](docs/remote-setup.md)**.

### Requirements

- Self-hosted NetBird **≥ v0.65** with the built-in reverse proxy (CrowdSec verdicts in access logs need **≥ v0.69**). Verified against **v0.81.3**.
- CrowdSec **≥ v1.6** Local API (verified against **v1.8.1**).
- Docker + Docker Compose v2.

### Project status

`0.1.0` – first public MVP. Backend, web UI and the Home Assistant integration are covered by automated tests; the backend was verified against a live NetBird 0.81.3 / CrowdSec 1.8.1 installation. See [docs/testing.md](docs/testing.md) for what was and was not tested.

### License

[Apache-2.0](LICENSE). Map data: Natural Earth (public domain) via world-atlas (ISC). NetBird and CrowdSec are trademarks of their respective owners; this project is not affiliated with them.
