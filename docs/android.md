# Android app

Kotlin · Jetpack Compose · Material 3 (dynamic colour, dark/light) · MVVM · Retrofit + kotlinx.serialization ·
Room (offline cache) · DataStore + Android Keystore (token encryption) · WorkManager · German and English.
`minSdk 26` (Android 8), `targetSdk 36`.

## Features

Dashboard (KPIs, traffic chart, top countries, domains), domain list + detail (status codes, top/suspicious URLs,
countries, CrowdSec scenarios), world map (tap a country, filter by domain, total/allowed/blocked), CrowdSec view
(alerts, local decisions, enforcement per layer), settings (notifications, theme, data source status, disconnect).
Time ranges: Live (15 s refresh), 1 h, 24 h, 7 d, 30 d, custom (date range picker).
When the backend is unreachable the last cached data is shown with a hint.

## Notifications

- **Instant push:** subscribe to your ntfy topic in the [ntfy app](https://ntfy.sh) – the backend publishes all alerts there.
- **In-app fallback:** a WorkManager job checks every ~15 minutes (Android minimum) for new notifications and
  notifies when the **backend is unreachable** (at most every 6 h). Configurable in the app settings.

## Build

Requirements: JDK 21, Android SDK platform 37.

```bash
cd android
./gradlew testDebugUnitTest assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk
```

## Release signing

Signing keys are **never** committed (`*.jks`, `*.keystore`, `keystore.properties` are git-ignored).

```bash
keytool -genkeypair -v -keystore ~/netshield-release.jks -alias netshield -keyalg RSA -keysize 4096 -validity 10000
```

Local release build – either environment variables or an untracked `android/keystore.properties`:

```properties
NETSHIELD_KEYSTORE_FILE=/home/you/netshield-release.jks
NETSHIELD_KEYSTORE_PASSWORD=…
NETSHIELD_KEY_ALIAS=netshield
NETSHIELD_KEY_PASSWORD=…
```

```bash
./gradlew assembleRelease
```

GitHub Releases: add the repository secrets `ANDROID_KEYSTORE_BASE64` (`base64 -w0 netshield-release.jks`),
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`. Pushing a tag `v*` builds a signed APK
and attaches it to the release (see `.github/workflows/release.yml`). Without the secrets an unsigned APK is attached.

## First start

Enter the backend URL and an API token (scope `read`). HTTPS is strongly recommended; plain `http://` is accepted
(with a warning) for access over a NetBird peer IP, where WireGuard already encrypts the traffic.
