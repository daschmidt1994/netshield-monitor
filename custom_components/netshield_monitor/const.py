"""Constants for the NetShield Monitor integration."""

from __future__ import annotations

DOMAIN = "netshield_monitor"
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DOMAIN_SENSORS = "domain_sensors"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600

EVENT_NOTIFICATION = f"{DOMAIN}_notification"
EVENT_SECURITY_ALERT = f"{DOMAIN}_security_alert"
