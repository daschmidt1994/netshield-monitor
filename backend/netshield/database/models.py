"""Database schema.

All timestamps are stored as integer UNIX epoch seconds (UTC). This keeps
time bucketing portable between SQLite and PostgreSQL (``ts - ts % bucket``).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    pass


# Request categories -------------------------------------------------------
CAT_VISITOR = "visitor"  # public client, nothing suspicious detected
CAT_SUSPICIOUS = "suspicious"  # scanner / bot heuristics matched
CAT_BLOCKED = "blocked"  # enforced by CrowdSec in the NetBird proxy (ban)
CAT_CHALLENGED = "challenged"  # CrowdSec captcha served by the NetBird proxy
CAT_INTERNAL = "internal"  # private / NetBird / configured internal networks
CATEGORIES = (CAT_VISITOR, CAT_SUSPICIOUS, CAT_BLOCKED, CAT_CHALLENGED, CAT_INTERNAL)


class ProxyRequest(Base):
    """One access-log entry from the NetBird reverse proxy (raw, short retention)."""

    __tablename__ = "proxy_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # NetBird access log id
    ts: Mapped[int] = mapped_column(BigInteger, index=True)
    service_id: Mapped[str | None] = mapped_column(String(64))
    host: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(512))
    protocol: Mapped[str] = mapped_column(String(8), default="http")
    status: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    bytes_up: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_down: Mapped[int] = mapped_column(BigInteger, default=0)
    ip: Mapped[str | None] = mapped_column(String(64))  # truncated unless ip_mode=full
    visitor_hash: Mapped[str | None] = mapped_column(String(32))  # daily-salted, irreversible after rotation
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(128))
    authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    verdict: Mapped[str | None] = mapped_column(String(32))  # crowdsec_ban / crowdsec_captcha
    observe_only: Mapped[bool] = mapped_column(Boolean, default=False)  # verdict in observe mode
    category: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (
        Index("ix_req_host_ts", "host", "ts"),
        Index("ix_req_cat_ts", "category", "ts"),
    )


class HourlyStat(Base):
    """Pre-aggregated counters per hour (long retention, no personal data)."""

    __tablename__ = "hourly_stats"

    hour: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    host: Mapped[str] = mapped_column(String(255), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), primary_key=True)  # "--" = unknown
    status: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(16), primary_key=True)
    observe_hits: Mapped[int] = mapped_column(Integer, default=0)
    count: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_down: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (Index("ix_hourly_host_hour", "host", "hour"),)


class DailyVisitors(Base):
    """Estimated unique visitors per day and host ('*' = all domains)."""

    __tablename__ = "daily_visitors"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD (configured timezone)
    host: Mapped[str] = mapped_column(String(255), primary_key=True)
    visitors: Mapped[int] = mapped_column(Integer, default=0)


class VisitorSalt(Base):
    __tablename__ = "visitor_salts"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    salt: Mapped[str] = mapped_column(String(64))


class Domain(Base):
    __tablename__ = "domains"

    host: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # netbird | manual | logs
    service_id: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # service enabled upstream
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # hidden in UI by the user
    crowdsec_mode: Mapped[str | None] = mapped_column(String(16))
    auth_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[int | None] = mapped_column(BigInteger)
    last_seen: Mapped[int | None] = mapped_column(BigInteger)
    removed_upstream: Mapped[bool] = mapped_column(Boolean, default=False)


class CrowdsecAlert(Base):
    __tablename__ = "crowdsec_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # LAPI alert id
    uuid: Mapped[str | None] = mapped_column(String(64))
    scenario: Mapped[str] = mapped_column(String(255), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    created_ts: Mapped[int] = mapped_column(BigInteger, index=True)
    start_ts: Mapped[int | None] = mapped_column(BigInteger)
    stop_ts: Mapped[int | None] = mapped_column(BigInteger)
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    source_scope: Mapped[str | None] = mapped_column(String(32))
    source_value: Mapped[str | None] = mapped_column(String(128))  # privacy-processed
    source_range: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(2))
    as_name: Mapped[str | None] = mapped_column(String(255))
    as_number: Mapped[str | None] = mapped_column(String(16))
    target_host: Mapped[str | None] = mapped_column(String(255))
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    decisions_count: Mapped[int] = mapped_column(Integer, default=0)
    decision_type: Mapped[str | None] = mapped_column(String(32))
    decision_duration: Mapped[str | None] = mapped_column(String(32))
    machine_id: Mapped[str | None] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(16), default="medium")


class CrowdsecDecision(Base):
    """Currently active decisions from local origins (snapshot, replaced each poll)."""

    __tablename__ = "crowdsec_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    origin: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(128))  # privacy-processed
    scenario: Mapped[str | None] = mapped_column(String(255))
    expires_ts: Mapped[int | None] = mapped_column(BigInteger)
    seen_ts: Mapped[int] = mapped_column(BigInteger)


class DecisionCount(Base):
    """Snapshot of active decision counts by origin/type (incl. community lists)."""

    __tablename__ = "crowdsec_decision_counts"

    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    origin: Mapped[str] = mapped_column(String(32), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)


class MetricSample(Base):
    """Selected CrowdSec Prometheus counters, sampled periodically."""

    __tablename__ = "metric_samples"

    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    labels: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[float] = mapped_column(Float)


class CollectorState(Base):
    __tablename__ = "collector_state"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="unknown")  # ok | error | disabled | backfill
    last_success_ts: Mapped[int | None] = mapped_column(BigInteger)
    last_error_ts: Mapped[int | None] = mapped_column(BigInteger)
    last_error: Mapped[str | None] = mapped_column(Text)
    items_total: Mapped[int] = mapped_column(BigInteger, default=0)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))  # info | warning | critical
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    host: Mapped[str | None] = mapped_column(String(255))
    dedup_key: Mapped[str] = mapped_column(String(255), index=True)
    delivered_ntfy: Mapped[bool] = mapped_column(Boolean, default=False)


class AdminUser(Base):
    __tablename__ = "admin_users"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_ts: Mapped[int] = mapped_column(BigInteger)


class Session(Base):
    __tablename__ = "sessions"

    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_ts: Mapped[int] = mapped_column(BigInteger)
    expires_ts: Mapped[int] = mapped_column(BigInteger, index=True)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    prefix: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scope: Mapped[str] = mapped_column(String(16), default="read")  # read | admin
    created_ts: Mapped[int] = mapped_column(BigInteger)
    last_used_ts: Mapped[int | None] = mapped_column(BigInteger)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class SettingKV(Base):
    """User-editable runtime settings (thresholds etc.). Never holds secrets."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)


class Meta(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
