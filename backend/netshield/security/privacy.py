"""IP address handling (GDPR): truncation, internal-network detection, visitor hashing."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
from functools import lru_cache


class IpPolicy:
    def __init__(self, mode: str, v4_prefix: int, v6_prefix: int, internal_networks: list[str]) -> None:
        self.mode = mode
        self.v4_prefix = v4_prefix
        self.v6_prefix = v6_prefix
        self.internal = [ipaddress.ip_network(n, strict=False) for n in internal_networks]

    @staticmethod
    @lru_cache(maxsize=65536)
    def _parse(value: str):
        try:
            return ipaddress.ip_address(value.strip())
        except ValueError:
            return None

    def is_internal(self, value: str | None) -> bool:
        ip = self._parse(value) if value else None
        if ip is None:
            return False
        if ip.is_loopback or ip.is_link_local:
            return True
        return any(ip in net for net in self.internal if net.version == ip.version)

    def display(self, value: str | None) -> str | None:
        """Return the IP as it may be stored/shown (truncated network unless mode=full)."""
        if not value:
            return None
        ip = self._parse(value)
        if ip is None:
            return None
        if self.mode == "full":
            return str(ip)
        prefix = self.v4_prefix if ip.version == 4 else self.v6_prefix
        net = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
        return str(net) if prefix < ip.max_prefixlen else str(ip)

    def display_range(self, value: str | None) -> str | None:
        """Truncate a CIDR range value (e.g. from CrowdSec) to at most the configured prefix."""
        if not value:
            return None
        try:
            net = ipaddress.ip_network(value.strip(), strict=False)
        except ValueError:
            return None
        if self.mode == "full":
            return str(net)
        prefix = self.v4_prefix if net.version == 4 else self.v6_prefix
        if net.prefixlen > prefix:
            net = net.supernet(new_prefix=prefix)
        return str(net)


def visitor_hash(salt: str, ip: str) -> str:
    """Daily-salted pseudonym; once the salt is deleted it cannot be linked back to the IP."""
    return hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]
