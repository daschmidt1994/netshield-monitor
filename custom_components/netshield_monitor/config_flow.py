"""Config flow for NetShield Monitor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NetShieldApi, NetShieldAuthError, NetShieldConnectionError
from .const import (
    CONF_DOMAIN_SENSORS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


async def _validate(hass, url: str, token: str, verify: bool) -> dict[str, Any]:
    api = NetShieldApi(async_get_clientsession(hass, verify_ssl=verify), url, token, verify)
    return await api.summary()


class NetShieldConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                errors[CONF_URL] = "invalid_url"
            else:
                try:
                    await _validate(self.hass, url, user_input[CONF_TOKEN], user_input[CONF_VERIFY_SSL])
                except NetShieldAuthError:
                    errors["base"] = "invalid_auth"
                except NetShieldConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(url.lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="NetShield Monitor", data={**user_input, CONF_URL: url})
        schema = vol.Schema({
            vol.Required(CONF_URL, default=(user_input or {}).get(CONF_URL, "https://")): str,
            vol.Required(CONF_TOKEN): str,
            vol.Required(CONF_VERIFY_SSL, default=True): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate(self.hass, entry.data[CONF_URL], user_input[CONF_TOKEN],
                                entry.data.get(CONF_VERIFY_SSL, True))
            except NetShieldAuthError:
                errors["base"] = "invalid_auth"
            except NetShieldConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]})
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
                                    errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NetShieldOptionsFlow()


class NetShieldOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            vol.Required(CONF_DOMAIN_SENSORS, default=opts.get(CONF_DOMAIN_SENSORS, True)): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
