"""Authentication and administration endpoints."""

from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..database.models import AdminUser, ApiToken, Domain, Session
from ..security.auth import (
    SESSION_COOKIE,
    Principal,
    new_api_token,
    require_admin,
    require_read,
    sha256,
    verify_password,
)
from ..services.runtime_settings import RuntimeSettings
from ..util import now_ts
from .deps import HOST_PATTERN, app_state

router = APIRouter(prefix="/api/v1")


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login", tags=["auth"])
async def login(body: LoginBody, request: Request, response: Response, st=Depends(app_state)):
    ip = st.ip_resolver.resolve(request)
    key = f"login:{ip}"
    if not st.login_limiter.hit(key):
        raise HTTPException(429, "too many login attempts, try again later")
    async with st.db.session() as s:
        user = await s.get(AdminUser, body.username)
        ok = verify_password(user.password_hash if user else None, body.password)
        if not ok:
            raise HTTPException(401, "invalid credentials")
        raw = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        now = now_ts()
        s.add(Session(id_hash=sha256(raw), username=user.username, csrf_token=csrf, created_ts=now,
                      expires_ts=now + st.settings.session_hours * 3600))
        await s.commit()
    response.set_cookie(SESSION_COOKIE, raw, max_age=st.settings.session_hours * 3600, httponly=True,
                        secure=st.settings.cookie_secure, samesite="strict", path="/")
    return {"username": user.username, "csrf_token": csrf}


@router.post("/auth/logout", tags=["auth"])
async def logout(request: Request, response: Response, st=Depends(app_state), p: Principal = Depends(require_read)):
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        async with st.db.session() as s:
            sess = await s.get(Session, sha256(raw))
            if sess:
                await s.delete(sess)
                await s.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me", tags=["auth"])
async def me(p: Principal = Depends(require_read)):
    return {"name": p.name, "kind": p.kind, "scope": p.scope, "csrf_token": p.csrf}


# --- API tokens ----------------------------------------------------------------------
class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[\w .\-]+$")
    scope: str = Field(default="read", pattern="^(read|admin)$")


@router.get("/admin/tokens", tags=["admin"])
async def list_tokens(st=Depends(app_state), _: Principal = Depends(require_admin)):
    async with st.db.session() as s:
        rows = (await s.execute(select(ApiToken).order_by(ApiToken.id))).scalars().all()
    return {"items": [{"id": t.id, "name": t.name, "prefix": t.prefix, "scope": t.scope, "created": t.created_ts,
                       "last_used": t.last_used_ts, "revoked": t.revoked} for t in rows]}


@router.post("/admin/tokens", tags=["admin"], status_code=201)
async def create_token(body: TokenCreate, st=Depends(app_state), _: Principal = Depends(require_admin)):
    raw = new_api_token()
    async with st.db.session() as s:
        t = ApiToken(name=body.name, prefix=raw[:12], token_hash=sha256(raw), scope=body.scope,
                     created_ts=now_ts())
        s.add(t)
        await s.commit()
        await s.refresh(t)
    # the plain token is returned exactly once
    return {"id": t.id, "name": t.name, "scope": t.scope, "token": raw}


@router.delete("/admin/tokens/{token_id}", tags=["admin"])
async def revoke_token(token_id: int, st=Depends(app_state), _: Principal = Depends(require_admin)):
    async with st.db.session() as s:
        t = await s.get(ApiToken, token_id)
        if not t:
            raise HTTPException(404, "token not found")
        t.revoked = True
        await s.commit()
    return {"ok": True}


# --- Domains (manual management) ----------------------------------------------------
class DomainCreate(BaseModel):
    host: str = Field(pattern=HOST_PATTERN)
    display_name: str | None = Field(default=None, max_length=255)


class DomainPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    hidden: bool | None = None


@router.post("/domains", tags=["domains"], status_code=201)
async def add_domain(body: DomainCreate, st=Depends(app_state), _: Principal = Depends(require_admin)):
    host = body.host.lower()
    async with st.db.session() as s:
        if await s.get(Domain, host):
            raise HTTPException(409, "domain exists")
        s.add(Domain(host=host, source="manual", display_name=body.display_name))
        await s.commit()
    return {"host": host}


@router.patch("/domains/{host}", tags=["domains"])
async def patch_domain(host: str, body: DomainPatch, st=Depends(app_state), _: Principal = Depends(require_admin)):
    if not re.match(HOST_PATTERN, host.lower()):
        raise HTTPException(422, "invalid host")
    async with st.db.session() as s:
        d = await s.get(Domain, host.lower())
        if not d:
            raise HTTPException(404, "unknown domain")
        if body.display_name is not None:
            d.display_name = body.display_name or None
        if body.hidden is not None:
            d.hidden = body.hidden
        await s.commit()
    return {"ok": True}


@router.delete("/domains/{host}", tags=["domains"])
async def delete_domain(host: str, st=Depends(app_state), _: Principal = Depends(require_admin)):
    async with st.db.session() as s:
        d = await s.get(Domain, host.lower())
        if not d:
            raise HTTPException(404, "unknown domain")
        if d.source == "netbird" and not d.removed_upstream:
            raise HTTPException(409, "domain is managed by NetBird – hide it instead")
        await s.delete(d)
        await s.commit()
    return {"ok": True}


# --- Runtime settings ------------------------------------------------------------------
@router.get("/admin/settings", tags=["admin"])
async def get_settings_(st=Depends(app_state), _: Principal = Depends(require_admin)):
    return (await st.runtime.get()).model_dump()


@router.put("/admin/settings", tags=["admin"])
async def put_settings(body: RuntimeSettings, st=Depends(app_state), _: Principal = Depends(require_admin)):
    return (await st.runtime.set(body)).model_dump()


@router.post("/admin/notifications/test", tags=["admin"])
async def test_notification(st=Depends(app_state), _: Principal = Depends(require_admin)):
    if not st.settings.ntfy_enabled:
        raise HTTPException(409, "ntfy is not configured (NETSHIELD_NTFY_URL / NETSHIELD_NTFY_TOPIC)")
    ok = await st.notifier.ntfy.send("NetShield Monitor", "Testbenachrichtigung / test notification", "info")
    if not ok:
        raise HTTPException(502, "ntfy delivery failed – check URL, topic and token")
    return {"ok": True}
