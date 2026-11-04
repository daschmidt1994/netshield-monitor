"""Async engine/session handling and dialect-portable upserts."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from sqlalchemy import event, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .models import SCHEMA_VERSION, Base, Meta


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.is_sqlite = url.startswith("sqlite")
        if self.is_sqlite:
            path = url.split("///", 1)[-1]
            if path and path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=not self.is_sqlite)
        if self.is_sqlite:

            @event.listens_for(self.engine.sync_engine, "connect")
            def _pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.close()

        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session() as s:
            row = await s.get(Meta, "schema_version")
            if row is None:
                s.add(Meta(key="schema_version", value=str(SCHEMA_VERSION)))
            elif int(row.value) > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema {row.value} is newer than this NetShield version ({SCHEMA_VERSION})"
                )
            await s.commit()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as s:
            yield s

    async def dispose(self) -> None:
        await self.engine.dispose()


def _insert_for(session: AsyncSession):
    name = session.bind.dialect.name if session.bind else "sqlite"
    return postgresql.insert if name == "postgresql" else sqlite.insert


async def upsert(
    session: AsyncSession,
    model,
    rows: Sequence[dict],
    key: Sequence[str],
    *,
    add: Sequence[str] = (),
    replace: Sequence[str] = (),
) -> None:
    """INSERT ... ON CONFLICT for SQLite and PostgreSQL.

    ``add`` columns are incremented by the new value, ``replace`` columns are overwritten.
    With neither, conflicting rows are ignored.
    """
    if not rows:
        return
    insert = _insert_for(session)
    table = model.__table__
    # chunk to stay below SQLite's variable limit
    cols = max(1, len(rows[0]))
    chunk = max(1, 30000 // cols)
    for i in range(0, len(rows), chunk):
        stmt = insert(table).values(list(rows[i : i + chunk]))
        if add or replace:
            set_ = {c: table.c[c] + stmt.excluded[c] for c in add}
            set_.update({c: stmt.excluded[c] for c in replace})
            stmt = stmt.on_conflict_do_update(index_elements=list(key), set_=set_)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=list(key))
        await session.execute(stmt)


async def existing_ids(session: AsyncSession, column, ids: Sequence) -> set:
    found: set = set()
    for i in range(0, len(ids), 500):
        res = await session.execute(select(column).where(column.in_(ids[i : i + 500])))
        found.update(res.scalars().all())
    return found
