# Screenshots

The repository contains no screenshots with real data. To create screenshots for documentation or a release:

1. Use a test instance or hide sensitive domains (Settings → Domains → Hide).
2. Keep `NETSHIELD_IP_MODE=truncate` so only networks are visible.
3. Web UI: browser at 1400×900 (desktop) and 390×844 (mobile emulation) for each page:
   Dashboard, Domains, domain detail, World map, CrowdSec, Settings – in light and dark mode.
4. Android: `adb exec-out screencap -p > dashboard.png` on a device/emulator for each tab.
5. Before publishing check every image for real domains, IPs, tokens or account names and blur/replace them
   (e.g. with `example.com`).
6. Store them under `docs/images/` and reference them from the README.

Automated option (requires Node and a Playwright Chromium): see the script in `docs/testing.md`.
