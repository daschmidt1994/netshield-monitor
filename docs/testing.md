# Test status (v0.1.0)

## Automated tests

| Component | Tests | Command |
|---|---|---|
| Backend | 26 pytest tests (collectors with recorded API shapes, stats, auth/CSRF/tokens, rate limit, XFF trust, notifier) | `cd backend && pip install -e .[dev] && pytest` |
| Web UI | TypeScript strict build | `cd web && npm ci && npm run build` |
| Home Assistant | 7 tests with `pytest-homeassistant-custom-component` (HA 2026.2.3): config/options/reauth flow, entities, events, offline, diagnostics redaction | `pytest -c pytest-ha.ini` |
| Android | 4 JVM unit tests; debug and release (R8) builds | `cd android && ./gradlew testDebugUnitTest assembleDebug assembleRelease` |

## Live verification (2026-11-04, NetBird 0.81.3, CrowdSec 1.8.1, Docker on Debian 13)

| Check | Result |
|---|---|
| `netshield check` against all sources | ✅ all OK |
| Backfill of 7 days NetBird access logs (~225 000 requests) | ✅ ~15 min, then live polling every 30 s |
| Requests in a 6 h window: NetBird API `total_records` vs. NetShield | ✅ 6 779 = 6 779 |
| CrowdSec-enforced 403s in the same window | ✅ 13 = 13 |
| Active local decisions: `cscli decisions list` vs. NetShield | ✅ 12 = 12 |
| Alerts in last 24 h: LAPI `since=24h` vs. NetShield | ≈ 139 vs. 142 – LAPI filters `since` on the alert start time, NetShield on `created_at`; alerts near the window edge differ |
| Docker image (non-root, read-only rootfs, healthcheck) | ✅ healthy |
| Web UI with real data (desktop, 390 px mobile, dark mode, de/en) | ✅ checked via headless Chromium, no console errors |
| Home Assistant summary endpoint with real data | ✅ |

## Not yet tested

- ⚠️ **Android app on a real device or emulator** (the build machine had too little RAM for an emulator).
  The app compiles, unit tests pass, API models were tested against real JSON shapes.
- ⚠️ Home Assistant integration inside a running Home Assistant instance (only the official test harness).
- ⚠️ PostgreSQL backend (`examples/docker-compose.postgres.yml`) – SQLite is the tested default.
- ⚠️ ntfy delivery against a real ntfy server (unit-tested with a mocked HTTP endpoint).
- ⚠️ GitHub workflows (CI, hassfest, HACS validation, release) – they run on the first push.
