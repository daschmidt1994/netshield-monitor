__version__ = "0.1.4"
# CrowdSec's LAPI rejects watcher logins whose User-Agent is not "<name>/<version>"
USER_AGENT = f"netshield-monitor/{__version__}"
