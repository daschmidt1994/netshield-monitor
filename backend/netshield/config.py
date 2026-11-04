"""Runtime configuration.

All settings come from environment variables prefixed with ``NETSHIELD_``.
Every secret can alternatively be supplied as a file via ``<NAME>_FILE``
(Docker secrets style), e.g. ``NETSHIELD_NETBIRD_TOKEN_FILE=/run/secrets/nb_token``.
"""

from __future__ import annotations

import ipaddress
import os
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_SECRET_FIELDS = (
    "database_url",  # may contain the PostgreSQL password
    "netbird_token",
    "crowdsec_bouncer_key",
    "crowdsec_machine_password",
    "ntfy_token",
    "admin_password",
)

DEFAULT_INTERNAL_NETWORKS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",  # CGNAT range used by NetBird peers
    "127.0.0.0/8",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NETSHIELD_", env_file=None, extra="ignore")

    # --- Core -------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:////data/netshield.db"
    timezone: str = "UTC"
    log_level: str = "INFO"
    base_path: str = ""  # reserved for running behind a sub-path

    # --- Web / API security ----------------------------------------------
    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    cookie_secure: bool = True
    session_hours: int = Field(default=12, ge=1, le=24 * 30)
    trusted_proxies: Annotated[list[str], NoDecode] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=240, ge=10)
    login_attempts_per_15min: int = Field(default=10, ge=3)

    # --- NetBird ------------------------------------------------------------
    netbird_url: str | None = None  # e.g. https://netbird.example.com
    netbird_token: SecretStr | None = None
    netbird_verify_tls: bool = True
    netbird_poll_seconds: int = Field(default=30, ge=10)
    netbird_services_poll_seconds: int = Field(default=300, ge=60)
    netbird_backfill_hours: int = Field(default=168, ge=0, le=24 * 31)
    netbird_max_pages_per_cycle: int = Field(default=20, ge=1, le=500)

    # --- CrowdSec ------------------------------------------------------------
    crowdsec_lapi_url: str | None = None  # e.g. http://crowdsec:8080
    crowdsec_bouncer_key: SecretStr | None = None
    crowdsec_machine_id: str | None = None
    crowdsec_machine_password: SecretStr | None = None
    crowdsec_metrics_url: str | None = None  # e.g. http://crowdsec:6060/metrics
    crowdsec_poll_seconds: int = Field(default=60, ge=15)
    crowdsec_backfill_hours: int = Field(default=168, ge=0, le=24 * 31)
    crowdsec_local_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["crowdsec", "cscli", "appsec", "console"]
    )
    critical_scenario_pattern: str = r"(cve|vpatch|appsec|bf|brute|exploit|sqli|xss|rce|lfi|log4j|shell)"

    # --- Privacy ---------------------------------------------------------------
    ip_mode: Literal["truncate", "full"] = "truncate"
    ipv4_prefix: int = Field(default=24, ge=8, le=32)
    ipv6_prefix: int = Field(default=48, ge=16, le=128)
    raw_retention_days: int = Field(default=14, ge=1, le=365)
    aggregate_retention_days: int = Field(default=365, ge=7, le=3650)
    alert_retention_days: int = Field(default=90, ge=1, le=3650)
    internal_networks: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_INTERNAL_NETWORKS)
    )

    # --- Notifications (ntfy) ------------------------------------------------
    ntfy_url: str | None = None  # e.g. https://ntfy.example.com
    ntfy_topic: str | None = None
    ntfy_token: SecretStr | None = None

    @field_validator("trusted_proxies", "internal_networks", "crowdsec_local_origins", mode="before")
    @classmethod
    def _csv(cls, v: object) -> object:
        return _split_csv(v)

    @field_validator("trusted_proxies", "internal_networks")
    @classmethod
    def _valid_networks(cls, v: list[str]) -> list[str]:
        for net in v:
            ipaddress.ip_network(net, strict=False)
        return v

    @field_validator("netbird_token", "crowdsec_bouncer_key", "crowdsec_machine_password", "ntfy_token",
                     "admin_password", mode="before")
    @classmethod
    def _empty_secret(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("netbird_url", "crowdsec_lapi_url", "crowdsec_metrics_url", "ntfy_url")
    @classmethod
    def _strip_slash(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @model_validator(mode="before")
    @classmethod
    def _load_secret_files(cls, data: dict) -> dict:
        data = dict(data) if isinstance(data, dict) else {}
        for name in _SECRET_FIELDS:
            path = os.environ.get(f"NETSHIELD_{name.upper()}_FILE")
            if path and not data.get(name):
                try:
                    with open(path, encoding="utf-8") as fh:
                        value = fh.read().strip()
                except FileNotFoundError:
                    continue
                if value:  # empty secret files mean "not configured"
                    data[name] = value
        return data

    # Convenience flags -----------------------------------------------------
    @property
    def netbird_enabled(self) -> bool:
        return bool(self.netbird_url and self.netbird_token)

    @property
    def crowdsec_decisions_enabled(self) -> bool:
        return bool(self.crowdsec_lapi_url and self.crowdsec_bouncer_key)

    @property
    def crowdsec_alerts_enabled(self) -> bool:
        return bool(self.crowdsec_lapi_url and self.crowdsec_machine_id and self.crowdsec_machine_password)

    @property
    def ntfy_enabled(self) -> bool:
        return bool(self.ntfy_url and self.ntfy_topic)


@lru_cache
def get_settings() -> Settings:
    return Settings()
