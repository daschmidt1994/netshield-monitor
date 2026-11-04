from __future__ import annotations

from fastapi import HTTPException, Query, Request

from ..services.stats import RangeError, TimeRange, resolve_range

HOST_PATTERN = r"^[a-z0-9.\-*_:]{1,255}$"


def get_range(
    range: str | None = Query(None, pattern="^(live|1h|24h|7d|30d|custom)$", description="Preset range"),
    from_: int | None = Query(None, alias="from", ge=0, description="Custom range start (epoch seconds)"),
    to: int | None = Query(None, ge=0, description="Custom range end (epoch seconds)"),
) -> TimeRange:
    try:
        return resolve_range(range, from_, to)
    except RangeError as exc:
        raise HTTPException(422, str(exc)) from exc


def host_param(host: str | None = Query(None, pattern=HOST_PATTERN, description="Filter by domain")) -> str | None:
    return host.lower() if host else None


def app_state(request: Request):
    return request.app.state
