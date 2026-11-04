"""Minimal async client for the NetShield Monitor REST API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class NetShieldError(Exception):
    """Base error."""


class NetShieldAuthError(NetShieldError):
    """Token rejected."""


class NetShieldConnectionError(NetShieldError):
    """Backend unreachable or returned an unexpected response."""


class NetShieldApi:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str, verify_ssl: bool = True) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token
        self._ssl = None if verify_ssl else False

    async def _get(self, path: str) -> Any:
        try:
            async with asyncio.timeout(20):
                resp = await self._session.get(
                    f"{self._url}{path}",
                    headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                    ssl=self._ssl,
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NetShieldConnectionError(f"cannot reach NetShield: {type(err).__name__}") from err
        async with resp:
            if resp.status in (401, 403):
                raise NetShieldAuthError("token rejected")
            if resp.status != 200:
                raise NetShieldConnectionError(f"unexpected HTTP status {resp.status}")
            try:
                return await resp.json()
            except (aiohttp.ContentTypeError, ValueError) as err:
                raise NetShieldConnectionError("invalid JSON response") from err

    async def summary(self) -> dict[str, Any]:
        return await self._get("/api/v1/ha/summary")

    async def health(self) -> dict[str, Any]:
        return await self._get("/api/v1/health")
