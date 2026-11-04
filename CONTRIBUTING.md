# Contributing / Mitwirken

Thanks for your interest! / Danke für dein Interesse!

1. Fork the repository and create a feature branch.
2. Never commit secrets, real domains or real IP addresses — use `example.com`
   and documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`).
3. Run the tests before opening a PR:
   - Backend: `cd backend && pip install -e .[dev] && pytest`
   - Home Assistant: `pytest custom_components` (see `docs/`)
   - Android: `cd android && ./gradlew test`
4. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:` …).
5. Do not add data that is not backed by a real source. No mock values in production code paths.

By contributing you agree that your contribution is licensed under Apache-2.0.
