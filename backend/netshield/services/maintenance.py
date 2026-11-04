"""Periodic maintenance: visitor counts, retention clean-up, salt rotation."""

from __future__ import annotations

import logging

from sqlalchemy import delete, distinct, func, select

from ..collectors.base import Collector
from ..config import Settings
from ..database import Database, upsert
from ..database.models import (
    CAT_VISITOR,
    CollectorState,
    CrowdsecAlert,
    DailyVisitors,
    DecisionCount,
    HourlyStat,
    MetricSample,
    Notification,
    ProxyRequest,
    Session,
    VisitorSalt,
)
from ..util import local_day, now_ts, start_of_local_day

log = logging.getLogger(__name__)


class Maintenance(Collector):
    name = "maintenance"
    interval = 600

    def __init__(self, db: Database, settings: Settings, salt_cache=None) -> None:
        super().__init__(db)
        self.settings = settings
        self.salt_cache = salt_cache

    async def run_once(self) -> int:
        await self.update_daily_visitors()
        await self.apply_retention()
        return 0

    async def update_daily_visitors(self, days: int | None = None) -> None:
        """(Re)compute visitors for every day still present in raw data."""
        tz = self.settings.timezone
        now = now_ts()
        days = days or self.settings.raw_retention_days
        async with self.db.session() as s:
            for i in range(days + 1):
                day_start = start_of_local_day(now - i * 86400, tz)
                day_end = start_of_local_day(day_start + 86400 + 7200, tz)  # DST-safe
                where = (ProxyRequest.ts >= day_start, ProxyRequest.ts < day_end,
                         ProxyRequest.category == CAT_VISITOR)
                rows = (await s.execute(
                    select(ProxyRequest.host, func.count(distinct(ProxyRequest.visitor_hash)))
                    .where(*where).group_by(ProxyRequest.host))).all()
                if not rows:
                    continue
                total = (await s.execute(select(func.count(distinct(ProxyRequest.visitor_hash)))
                                         .where(*where))).scalar() or 0
                day = local_day(day_start, tz)
                data = [{"day": day, "host": h, "visitors": int(n)} for h, n in rows]
                data.append({"day": day, "host": "*", "visitors": int(total)})
                await upsert(s, DailyVisitors, data, ["day", "host"], replace=["visitors"])
            await s.commit()

    async def apply_retention(self) -> None:
        st = self.settings
        now = now_ts()
        tz = st.timezone
        async with self.db.session() as s:
            raw_cut = now - st.raw_retention_days * 86400
            r1 = await s.execute(delete(ProxyRequest).where(ProxyRequest.ts < raw_cut))
            agg_cut = now - st.aggregate_retention_days * 86400
            await s.execute(delete(HourlyStat).where(HourlyStat.hour < agg_cut))
            await s.execute(delete(DailyVisitors).where(DailyVisitors.day < local_day(agg_cut, tz)))
            alert_cut = now - st.alert_retention_days * 86400
            await s.execute(delete(CrowdsecAlert).where(CrowdsecAlert.created_ts < alert_cut))
            await s.execute(delete(DecisionCount).where(DecisionCount.ts < raw_cut))
            await s.execute(delete(MetricSample).where(MetricSample.ts < raw_cut))
            await s.execute(delete(Notification).where(Notification.ts < now - 90 * 86400))
            await s.execute(delete(Session).where(Session.expires_ts < now))
            # Salts are only needed while a day can still receive requests (incl. late log delivery).
            yesterday = local_day(now - 86400, tz)
            nb = await s.get(CollectorState, "netbird_access_logs")
            backfilling = nb is not None and nb.status == "backfill"
            old = []
            if not backfilling:
                old = (await s.execute(select(VisitorSalt.day).where(VisitorSalt.day < yesterday))).scalars().all()
            if old:
                await s.execute(delete(VisitorSalt).where(VisitorSalt.day.in_(old)))
                if self.salt_cache:
                    for d in old:
                        self.salt_cache.forget(d)
            await s.commit()
        if r1.rowcount:
            log.info("retention: removed %s raw requests", r1.rowcount)
