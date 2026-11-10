"""A collector loop must survive database outages and report itself when it is dead.

Regression: during a nightly container update PostgreSQL was briefly unreachable. The
collector's run failed, and recording that failure (``_mark``) failed too. The second
exception escaped ``run_safe`` and silently ended the collector task while the container
stayed "healthy" for days.
"""

import asyncio

from httpx import ASGITransport, AsyncClient

from netshield.app import create_app
from netshield.collectors.base import Collector


class FlakyCollector(Collector):
    name = "flaky"
    interval = 0

    def __init__(self, db, fail_runs: int) -> None:
        super().__init__(db)
        self.calls = 0
        self.fail_runs = fail_runs

    async def run_once(self) -> int:
        self.calls += 1
        if self.calls <= self.fail_runs:
            raise ConnectionRefusedError(111, "Connection refused")
        return 0


async def _db_down(*_args, **_kwargs):
    raise ConnectionRefusedError(111, "Connection refused")


async def test_run_safe_survives_failing_state_write(db):
    col = FlakyCollector(db, fail_runs=1)
    col._mark = _db_down  # the database is gone, so the failure can't be recorded either
    assert await col.run_safe() == 0  # must not raise


async def test_loop_keeps_running_while_database_is_down(db, monkeypatch):
    monkeypatch.setattr("netshield.collectors.base.random.uniform", lambda *_: 0)
    col = FlakyCollector(db, fail_runs=2)
    col._mark = _db_down
    col.start()
    try:
        for _ in range(200):
            if col.calls >= 3:
                break
            await asyncio.sleep(0.01)
        assert col.calls >= 3
        assert col.alive
    finally:
        await col.stop()


async def test_health_reports_dead_collector(settings):
    app = create_app(settings, start_collectors=False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/v1/health")).status_code == 200

            dead = FlakyCollector(app.state.db, fail_runs=0)

            async def finished():
                return None

            dead._task = asyncio.create_task(finished())
            await dead._task
            app.state.collectors.append(dead)

            r = await client.get("/api/v1/health")
            assert r.status_code == 503
            assert r.json()["status"] == "degraded"
            assert set(r.json()) == {"status", "version", "time"}  # still no internal details
