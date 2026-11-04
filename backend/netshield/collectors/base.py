"""Collector base class: periodic loop, persisted state, error backoff."""

from __future__ import annotations

import asyncio
import logging
import random

from ..database import Database
from ..database.models import CollectorState
from ..util import now_ts

log = logging.getLogger(__name__)


class CollectorError(Exception):
    """Expected, user-facing collector failure (bad credentials, unreachable source...)."""


class Collector:
    name: str = "base"
    interval: int = 60

    def __init__(self, db: Database) -> None:
        self.db = db
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._failures = 0
        self.listeners: list = []  # callables notified after successful runs with new data

    @property
    def enabled(self) -> bool:
        return True

    async def run_once(self) -> int:
        """Collect once. Returns the number of new items."""
        raise NotImplementedError

    # --- state helpers -----------------------------------------------------
    async def get_state(self) -> CollectorState:
        async with self.db.session() as s:
            st = await s.get(CollectorState, self.name)
            if st is None:
                st = CollectorState(name=self.name, status="unknown", items_total=0)
                s.add(st)
                await s.commit()
            return st

    async def save_cursor(self, cursor: dict) -> None:
        async with self.db.session() as s:
            st = await s.get(CollectorState, self.name)
            st.cursor = cursor
            await s.commit()

    async def _mark(self, ok: bool, *, error: str | None = None, items: int = 0, status: str | None = None):
        async with self.db.session() as s:
            st = await s.get(CollectorState, self.name) or CollectorState(name=self.name, items_total=0)
            if ok:
                st.status = status or "ok"
                st.last_success_ts = now_ts()
                st.items_total = (st.items_total or 0) + items
            else:
                st.status = status or "error"
                st.last_error_ts = now_ts()
                st.last_error = (error or "unknown error")[:1000]
            s.add(st)
            await s.commit()

    # --- loop ----------------------------------------------------------------
    async def run_safe(self) -> int:
        try:
            n = await self.run_once()
        except CollectorError as exc:
            self._failures += 1
            log.warning("collector %s failed: %s", self.name, exc)
            await self._mark(False, error=str(exc))
            return 0
        except Exception as exc:  # keep the loop alive on unexpected errors
            self._failures += 1
            log.exception("collector %s crashed", self.name)
            await self._mark(False, error=f"{type(exc).__name__}: {exc}")
            return 0
        self._failures = 0
        await self._mark(True, items=n, status=getattr(self, "_status_override", None))
        if n:
            for cb in self.listeners:
                try:
                    await cb(self.name, n)
                except Exception:
                    log.exception("listener failed for %s", self.name)
        return n

    async def _loop(self) -> None:
        # small jitter so collectors don't all fire at the same moment
        await asyncio.sleep(random.uniform(0, 2))  # noqa: S311 - not security relevant
        while not self._stop.is_set():
            await self.run_safe()
            delay = self.interval
            if self._failures:
                delay = min(self.interval * (2 ** min(self._failures, 5)), 900)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except TimeoutError:
                pass

    def start(self) -> None:
        if not self.enabled:
            asyncio.get_event_loop().create_task(self._mark(False, error="not configured", status="disabled"))
            return
        self._task = asyncio.create_task(self._loop(), name=f"collector-{self.name}")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: S110 - shutdown
                pass
