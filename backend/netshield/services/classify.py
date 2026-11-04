"""Request classification: visitor vs. bot/scanner vs. internal vs. CrowdSec enforcement.

NetBird access logs contain no User-Agent, so bot detection is heuristic
(path patterns). Results are labelled as estimates in the UI.
"""

from __future__ import annotations

import re

from ..database.models import CAT_BLOCKED, CAT_CHALLENGED, CAT_INTERNAL, CAT_SUSPICIOUS, CAT_VISITOR

# Paths that legitimate visitors of typical self-hosted apps practically never request.
SCANNER_PATTERNS = [
    r"/\.env",
    r"/\.git(/|$)",
    r"/\.svn",
    r"/\.hg",
    r"/\.aws",
    r"/\.ssh",
    r"/\.DS_Store",
    r"/wp-(login|admin|content|includes|config)",
    r"/xmlrpc\.php",
    r"/phpmyadmin",
    r"/pma(/|$)",
    r"/phpinfo",
    r"/cgi-bin/",
    r"/boaform",
    r"/HNAP1",
    r"/actuator(/|$)",
    r"/vendor/phpunit",
    r"/solr/",
    r"/owa/",
    r"/autodiscover",
    r"/ecp/",
    r"/remote/login",
    r"/geoserver",
    r"/druid/",
    r"/console(/|$)",
    r"/telescope",
    r"/_profiler",
    r"/server-status",
    r"/config\.(json|php|yml|yaml)$",
    r"/(backup|dump|db|database)\.(sql|zip|tar|gz)",
    r"\.(asp|aspx|jsp|cgi)$",
    r"/shell",
    r"/setup\.cgi",
    r"/manager/html",
    r"/jira/",
    r"/s/\w+/_/;/",  # Jira CVE-2021-26086 probing
    r"\.\./",
]
_SCANNER_RE = re.compile("|".join(f"(?:{p})" for p in SCANNER_PATTERNS), re.IGNORECASE)
_UNUSUAL_METHODS = {"CONNECT", "TRACE", "PROPFIND_SCAN", "DEBUG"}


def looks_like_scanner(path: str, method: str) -> bool:
    return bool(_SCANNER_RE.search(path or "")) or method.upper() in _UNUSUAL_METHODS


def classify(*, path: str, method: str, verdict: str | None, observe_only: bool, internal: bool) -> str:
    if verdict and not observe_only:
        return CAT_CHALLENGED if "captcha" in verdict else CAT_BLOCKED
    if internal:
        return CAT_INTERNAL
    if verdict:  # observe mode: CrowdSec flagged the IP but the request was let through
        return CAT_SUSPICIOUS
    if looks_like_scanner(path, method):
        return CAT_SUSPICIOUS
    return CAT_VISITOR
