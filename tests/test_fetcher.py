import pytest

from ikman.config import CrawlConfig
from ikman.fetcher import Fetcher, RobotsGate


class FakeResponse:
    def __init__(self, status, text="", headers=None, url="https://ikman.lk/x"):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self.url = url


class FakeSession:
    """Serves queued responses; records what was asked for."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requested = []
        self.headers = {}

    def get(self, url, timeout=None, allow_redirects=None):
        self.requested.append(url)
        return self.responses.pop(0) if self.responses else FakeResponse(200, "ok")

    def close(self):
        pass


ROBOTS_ALLOW = "User-agent: *\nAllow: /\nCrawl-delay: 2\n"
ROBOTS_DENY_ADS = "User-agent: *\nDisallow: /en/ad/\n"


def test_robots_allows_and_reads_crawl_delay():
    gate = RobotsGate(FakeSession(FakeResponse(200, ROBOTS_ALLOW)), True)
    assert gate.allows("https://ikman.lk/en/ads/ratnapura", "bot") is True
    assert gate.crawl_delay == 2.0


def test_robots_disallowed_path_is_refused():
    gate = RobotsGate(FakeSession(FakeResponse(200, ROBOTS_DENY_ADS)), True)
    assert gate.allows("https://ikman.lk/en/ads/ratnapura", "bot") is True
    assert gate.allows("https://ikman.lk/en/ad/some-advert", "bot") is False


def test_robots_fails_closed_when_forbidden():
    """A 403 on robots.txt must not be read as permission."""
    gate = RobotsGate(FakeSession(FakeResponse(403)), True)
    assert gate.allows("https://ikman.lk/en/ads/ratnapura", "bot") is False


def test_robots_404_means_no_restrictions():
    gate = RobotsGate(FakeSession(FakeResponse(404)), True)
    assert gate.allows("https://ikman.lk/en/ads/ratnapura", "bot") is True


def test_robots_is_fetched_once_per_host():
    session = FakeSession(FakeResponse(200, ROBOTS_ALLOW))
    gate = RobotsGate(session, True)
    for _ in range(3):
        gate.allows("https://ikman.lk/en/ads/ratnapura", "bot")
    assert session.requested.count("https://ikman.lk/robots.txt") == 1


def test_disabled_gate_allows_everything():
    gate = RobotsGate(FakeSession(FakeResponse(200, "User-agent: *\nDisallow: /")), False)
    assert gate.allows("https://ikman.lk/anything", "bot") is True


def _fetcher(tmp_path, *responses, **kwargs):
    config = CrawlConfig(delay_seconds=0, delay_jitter=0, obey_robots=False, **kwargs)
    fetcher = Fetcher(config, cache_dir=tmp_path / "cache")
    fetcher.session = FakeSession(*responses)
    fetcher.robots = RobotsGate(fetcher.session, enabled=False)
    return fetcher


def test_cache_prevents_a_second_request(tmp_path):
    fetcher = _fetcher(tmp_path, FakeResponse(200, "<html>page</html>"))
    first = fetcher.get("https://ikman.lk/en/ads/ratnapura")
    second = fetcher.get("https://ikman.lk/en/ads/ratnapura")
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.text == "<html>page</html>"
    assert fetcher.stats["cache_hits"] == 1
    assert len(fetcher.session.requested) == 1


def test_retries_then_succeeds(tmp_path):
    fetcher = _fetcher(
        tmp_path,
        FakeResponse(503, headers={"Retry-After": "0"}),
        FakeResponse(200, "<html>ok</html>"),
        max_retries=3,
    )
    resp = fetcher.get("https://ikman.lk/en/ads/ratnapura")
    assert resp.status == 200
    assert len(fetcher.session.requested) == 2


def test_client_error_is_returned_not_retried(tmp_path):
    fetcher = _fetcher(tmp_path, FakeResponse(404, "missing"), max_retries=3)
    resp = fetcher.get("https://ikman.lk/en/ad/gone")
    assert resp.status == 404
    assert len(fetcher.session.requested) == 1
    assert fetcher.stats["errors"] == 1


def test_error_responses_are_not_cached(tmp_path):
    fetcher = _fetcher(tmp_path, FakeResponse(404, "missing"), FakeResponse(200, "back"))
    assert fetcher.get("https://ikman.lk/en/ad/x").status == 404
    assert fetcher.get("https://ikman.lk/en/ad/x").status == 200


def test_robots_block_raises(tmp_path):
    from ikman.fetcher import RobotsDisallowed
    config = CrawlConfig(delay_seconds=0, delay_jitter=0, obey_robots=True)
    fetcher = Fetcher(config, cache_dir=tmp_path / "cache")
    fetcher.session = FakeSession(FakeResponse(200, ROBOTS_DENY_ADS))
    fetcher.robots = RobotsGate(fetcher.session, enabled=True)
    with pytest.raises(RobotsDisallowed):
        fetcher.get("https://ikman.lk/en/ad/blocked-advert")
    assert fetcher.stats["robots_blocked"] == 1
