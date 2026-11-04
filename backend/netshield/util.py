"""Small shared helpers: time handling, Go durations."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def now_ts() -> int:
    return int(time.time())


def parse_rfc3339(value: str | None) -> int | None:
    """Parse RFC3339 timestamps with up to nanosecond precision to epoch seconds."""
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    # Python only supports microseconds: cut excess fractional digits
    m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", v)
    if m:
        frac = (m.group(2) or "")[:7]
        v = f"{m.group(1)}{frac}{m.group(3)}"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


def to_rfc3339(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_day(ts: int, tz: str) -> str:
    return datetime.fromtimestamp(ts, ZoneInfo(tz)).strftime("%Y-%m-%d")


def start_of_local_day(ts: int, tz: str) -> int:
    dt = datetime.fromtimestamp(ts, ZoneInfo(tz)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(dt.timestamp())


_GO_DURATION = re.compile(r"(-?\d+(?:\.\d+)?)(h|ms|m|s|us|µs|ns)")
_UNIT = {"h": 3600, "m": 60, "s": 1, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9}


def parse_go_duration(value: str | None) -> float | None:
    """Parse Go duration strings like ``167h59m3.5s`` (used by CrowdSec)."""
    if not value:
        return None
    parts = _GO_DURATION.findall(value)
    if not parts:
        return None
    return sum(float(n) * _UNIT[u] for n, u in parts)
