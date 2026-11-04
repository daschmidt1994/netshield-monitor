"""Authentication: admin sessions (web UI) and scoped API tokens (Android, Home Assistant)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from ..database.models import AdminUser, ApiToken, Session
from ..util import now_ts

SESSION_COOKIE = "nsm_session"
CSRF_HEADER = "X-CSRF-Token"
TOKEN_PREFIX = "nsm_"  # noqa: S105 - public prefix, not a secret
_ph = PasswordHasher()
# Pre-computed hash for constant-time behaviour when the user does not exist
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    try:
        return _ph.verify(stored or _DUMMY_HASH, password) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_api_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


@dataclass
class Principal:
    kind: str  # session | token
    name: str
    scope: str  # read | admin
    csrf: str | None = None
    token_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.scope == "admin"


async def create_admin(db, username: str, password: str, *, replace: bool = False) -> None:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    async with db.session() as s:
        row = await s.get(AdminUser, username)
        if row and not replace:
            raise ValueError("user exists")
        if row:
            row.password_hash = hash_password(password)
            # invalidate existing sessions after a password change
            for sess in (await s.execute(select(Session).where(Session.username == username))).scalars():
                await s.delete(sess)
        else:
            s.add(AdminUser(username=username, password_hash=hash_password(password), created_ts=now_ts()))
        await s.commit()


async def admin_exists(db) -> bool:
    async with db.session() as s:
        return (await s.execute(select(AdminUser.username).limit(1))).first() is not None


async def authenticate(request: Request) -> Principal | None:
    db = request.app.state.db
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        raw = auth[7:].strip()
        if not raw.startswith(TOKEN_PREFIX):
            return None
        async with db.session() as s:
            tok = (await s.execute(select(ApiToken).where(ApiToken.token_hash == sha256(raw)))).scalar_one_or_none()
            if tok is None or tok.revoked:
                return None
            now = now_ts()
            if not tok.last_used_ts or now - tok.last_used_ts > 60:
                tok.last_used_ts = now
                await s.commit()
            return Principal(kind="token", name=tok.name, scope=tok.scope, token_id=tok.id)
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        async with db.session() as s:
            sess = await s.get(Session, sha256(cookie))
            if sess is None or sess.expires_ts < now_ts():
                return None
            return Principal(kind="session", name=sess.username, scope="admin", csrf=sess.csrf_token)
    return None


async def require_read(request: Request) -> Principal:
    p = await authenticate(request)
    if p is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    if p.kind == "session" and request.method not in ("GET", "HEAD", "OPTIONS"):
        sent = request.headers.get(CSRF_HEADER, "")
        if not p.csrf or not hmac.compare_digest(sent, p.csrf):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    request.state.principal = p
    return p


async def require_admin(p: Principal = Depends(require_read)) -> Principal:
    if not p.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin scope required")
    return p
