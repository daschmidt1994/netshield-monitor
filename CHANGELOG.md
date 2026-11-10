# Changelog

All notable changes are documented here. The project follows [Semantic Versioning](https://semver.org/).

## [0.1.4] – 2026-11-10

### Fixed
- Collectors no longer die when the database is briefly unreachable (e.g. PostgreSQL restarting during a
  container update): a failed state write is logged instead of ending the collector loop, and the loop itself
  survives any unexpected error. Previously the NetBird access-log collector stopped silently and all traffic
  statistics fell to zero until the container was restarted.
- `/api/v1/health` answers `503` (`status: degraded`) when a started collector is no longer running, so the
  container healthcheck turns unhealthy instead of hiding a dead collector.

## [0.1.3] – 2026-11-04

### Added
- Android: settings show app and server version; "Check for updates" looks up the latest GitHub release and
  downloads the new APK.

### Fixed
- Release APKs are now signed; the release workflow fails instead of publishing an unsigned APK.

## [0.1.2] – 2026-11-04

### Added
- Android: world map supports pinch-to-zoom, panning while zoomed and double-tap zoom/reset; legend for the
  "all / blocked" numbers in the country list.
- Optional remote CrowdSec metrics: `docker/crowdsec-bridge/docker-compose.metrics.yml` exposes `:6060` via the
  NetBird IP (`:18081`).

## [0.1.1] – 2026-11-04

### Fixed
- Sanitize NUL bytes in NetBird access-log text fields before PostgreSQL writes so malicious request paths cannot stall the collector.

## [0.1.0] – 2026-11-04

### Added
- Backend: NetBird proxy access-log and services collectors, CrowdSec alerts/decisions/metrics collectors,
  SQLite/PostgreSQL storage with hourly aggregates, REST API + SSE, admin sessions and API tokens,
  rate limiting, retention and IP truncation, ntfy notifications.
- Web UI: dashboard, domains, domain detail, world map, CrowdSec, requests, settings (de/en, dark/light).
- Android app: dashboard, domains, map, CrowdSec, settings, offline cache, background checks.
- Home Assistant custom integration with config flow, sensors, binary sensors, events, diagnostics.
- Docker image, Compose file, CI and release workflows.
