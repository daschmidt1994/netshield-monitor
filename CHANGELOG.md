# Changelog

All notable changes are documented here. The project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] – 2026-11-04

### Added
- Backend: NetBird proxy access-log and services collectors, CrowdSec alerts/decisions/metrics collectors,
  SQLite/PostgreSQL storage with hourly aggregates, REST API + SSE, admin sessions and API tokens,
  rate limiting, retention and IP truncation, ntfy notifications.
- Web UI: dashboard, domains, domain detail, world map, CrowdSec, requests, settings (de/en, dark/light).
- Android app: dashboard, domains, map, CrowdSec, settings, offline cache, background checks.
- Home Assistant custom integration with config flow, sensors, binary sensors, events, diagnostics.
- Docker image, Compose file, CI and release workflows.
