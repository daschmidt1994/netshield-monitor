from netshield.database.models import CAT_BLOCKED, CAT_CHALLENGED, CAT_INTERNAL, CAT_SUSPICIOUS, CAT_VISITOR
from netshield.security.privacy import IpPolicy, visitor_hash
from netshield.services.classify import classify, looks_like_scanner
from netshield.util import parse_go_duration, parse_rfc3339

POLICY = IpPolicy("truncate", 24, 48, ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10"])


def test_truncation():
    assert POLICY.display("203.0.113.77") == "203.0.113.0/24"
    assert POLICY.display("2001:db8:1234:5678::1") == "2001:db8:1234::/48"
    assert POLICY.display("not-an-ip") is None
    assert IpPolicy("full", 24, 48, []).display("203.0.113.77") == "203.0.113.77"
    assert POLICY.display_range("203.0.113.128/25") == "203.0.113.0/24"
    assert POLICY.display_range("198.51.0.0/16") == "198.51.0.0/16"


def test_internal_networks():
    assert POLICY.is_internal("172.30.0.1")
    assert POLICY.is_internal("100.64.1.2")
    assert POLICY.is_internal("127.0.0.1")
    assert not POLICY.is_internal("198.51.100.1")
    assert not POLICY.is_internal("")


def test_visitor_hash_depends_on_salt():
    assert visitor_hash("a", "198.51.100.1") == visitor_hash("a", "198.51.100.1")
    assert visitor_hash("a", "198.51.100.1") != visitor_hash("b", "198.51.100.1")


def test_classification():
    kw = dict(method="GET", observe_only=False, internal=False)
    assert classify(path="/", verdict=None, **kw) == CAT_VISITOR
    assert classify(path="/.env", verdict=None, **kw) == CAT_SUSPICIOUS
    assert classify(path="/wp-login.php", verdict=None, **kw) == CAT_SUSPICIOUS
    assert classify(path="/", verdict="crowdsec_ban", **kw) == CAT_BLOCKED
    assert classify(path="/", verdict="crowdsec_captcha", **kw) == CAT_CHALLENGED
    assert classify(path="/", verdict="crowdsec_ban", method="GET", observe_only=True, internal=False) \
        == CAT_SUSPICIOUS
    assert classify(path="/healthz", verdict=None, method="GET", observe_only=False, internal=True) \
        == CAT_INTERNAL
    assert not looks_like_scanner("/api/health", "GET")
    assert looks_like_scanner("/s/abc/_/;/WEB-INF/web.xml", "GET")


def test_time_parsing():
    assert parse_rfc3339("2026-11-04T09:17:57.740739519Z") == 1793783877
    assert parse_rfc3339("2026-11-04T09:17:57Z") == 1793783877
    assert parse_rfc3339(None) is None
    assert parse_go_duration("3m58.5s") == 238.5
    assert parse_go_duration("167h59m") == 167 * 3600 + 59 * 60
    assert parse_go_duration("") is None
