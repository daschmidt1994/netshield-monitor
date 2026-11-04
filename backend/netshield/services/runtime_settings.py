"""User-editable settings stored in the database (thresholds, notification switches).

Secrets and data-source credentials are *not* editable here – they live in the environment only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select

from ..database import Database
from ..database.models import SettingKV


class NotificationSettings(BaseModel):
    enabled: bool = True
    critical_alerts: bool = True
    min_alert_severity: str = Field(default="critical", pattern="^(critical|high|low)$")
    request_spike: bool = True
    request_spike_factor: float = Field(default=4.0, ge=1.5, le=100)
    request_spike_min_per_5min: int = Field(default=600, ge=10)
    attack_spike: bool = True
    attack_spike_min_per_5min: int = Field(default=150, ge=5)
    domain_outage: bool = True
    domain_outage_error_ratio: float = Field(default=0.6, ge=0.05, le=1)
    domain_outage_min_requests: int = Field(default=20, ge=3)
    scanner_pattern: bool = True
    scanner_404_per_source_5min: int = Field(default=60, ge=10)
    source_errors: bool = True
    source_error_minutes: int = Field(default=10, ge=2, le=1440)
    cooldown_minutes: int = Field(default=30, ge=1, le=1440)


class RuntimeSettings(BaseModel):
    notifications: NotificationSettings = NotificationSettings()


class RuntimeSettingsStore:
    KEY = "runtime"

    def __init__(self, db: Database) -> None:
        self.db = db
        self._cache: RuntimeSettings | None = None

    async def get(self) -> RuntimeSettings:
        if self._cache is None:
            async with self.db.session() as s:
                row = (await s.execute(select(SettingKV).where(SettingKV.key == self.KEY))).scalar_one_or_none()
                self._cache = RuntimeSettings.model_validate(row.value) if row and row.value else RuntimeSettings()
        return self._cache

    async def set(self, value: RuntimeSettings) -> RuntimeSettings:
        async with self.db.session() as s:
            row = await s.get(SettingKV, self.KEY)
            if row is None:
                s.add(SettingKV(key=self.KEY, value=value.model_dump()))
            else:
                row.value = value.model_dump()
            await s.commit()
        self._cache = value
        return value
