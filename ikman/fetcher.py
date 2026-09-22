"""HTTP access: robots.txt gate, retries with backoff, rate limiting, disk cache."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import hashlib
import logging
import random
import time

import requests

from .config import CrawlConfig

log = logging.getLogger("ikman.fetcher")

RETRY_STATUS = {429, 500, 502, 503, 504, 408, 522, 524}


class RobotsDisallowed(RuntimeError):
    """Raised when robots.txt forbids a URL and obey_robots is on."""


class FetchError(RuntimeError):
    pass


@dataclass
class Response:
    url: str
    status: int
    text: str
    from_cache: bool = False


class RobotsGate:
    """robots.txt lookup, cached per host. Fail-closed when obeying robots.

    If robots.txt cannot be read we refuse rather than assume permission; that
    is the safe default for a tool pointed at someone else's site.
    """

    def __init__(self, session: requests.Session, enabled: bool = True,
                 timeout: float = 15.0):
        self.session = session
        self.enabled = enabled
        self.timeout = timeout
        self._parsers: dict[str, RobotFileParser | None] = {}
        self.crawl_delay: float | None = None

    def _parser(self, url: str) -> RobotFileParser | None:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin in self._parsers:
            return self._parsers[origin]

        parser: RobotFileParser | None = None
        try:
            resp = self.session.get(urljoin(origin, "/robots.txt"), timeout=self.timeout)
            if resp.status_code == 200:
                parser = RobotFileParser()
                parser.parse(resp.text.splitlines())
            elif resp.status_code in (401, 403):
                parser = None            # treated as "everything disallowed"
            else:
                parser = RobotFileParser()
                parser.parse([])         # 404 -> no restrictions published
        except requests.RequestException as exc:
            log.warning("could not fetch robots.txt for %s: %s", origin, exc)
            parser = None

        self._parsers[origin] = parser
        return parser

    def allows(self, url: str, user_agent: str) -> bool:
        if not self.enabled:
            return True
        parser = self._parser(url)
        if parser is None:
            return False
        delay = parser.crawl_delay(user_agent) or parser.crawl_delay("*")
        if delay:
            self.crawl_delay = float(delay)
        return parser.can_fetch(user_agent, url)


class Fetcher:
    """Single-threaded, rate-limited GET with retries and an optional disk cache."""

    def __init__(self, config: CrawlConfig, cache_dir: str | Path | None = "cache"):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,si;q=0.8",
        })
        self.robots = RobotsGate(self.session, config.obey_robots,
                                 config.timeout_seconds)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0
        self.stats: dict[str, int] = {
            "requests": 0, "cache_hits": 0, "errors": 0, "robots_blocked": 0,
        }

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()}.html"

    def _sleep(self) -> None:
        """Honour the larger of our configured delay and any robots Crawl-delay."""
        interval = self.config.delay_seconds
        if self.robots.crawl_delay:
            interval = max(interval, self.robots.crawl_delay)
        elapsed = time.monotonic() - self._last_request
        wait = interval - elapsed + random.uniform(0, self.config.delay_jitter)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, use_cache: bool = True) -> Response:
        cache_path = self._cache_path(url)
        if use_cache and cache_path and cache_path.exists():
            self.stats["cache_hits"] += 1
            return Response(url, 200, cache_path.read_text(encoding="utf-8"), True)

        if not self.robots.allows(url, self.config.user_agent):
            self.stats["robots_blocked"] += 1
            raise RobotsDisallowed(f"robots.txt disallows {url}")

        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            self._sleep()
            self._last_request = time.monotonic()
            try:
                resp = self.session.get(url, timeout=self.config.timeout_seconds,
                                        allow_redirects=True)
                self.stats["requests"] += 1
            except requests.RequestException as exc:
                last_error = exc
                log.warning("attempt %d/%d failed for %s: %s",
                            attempt, self.config.max_retries, url, exc)
            else:
                if resp.status_code in RETRY_STATUS:
                    retry_after = resp.headers.get("Retry-After")
                    backoff = float(retry_after) if (retry_after or "").isdigit() \
                        else 2 ** attempt
                    log.warning("HTTP %s for %s; backing off %.1fs",
                                resp.status_code, url, backoff)
                    last_error = FetchError(f"HTTP {resp.status_code}")
                    time.sleep(backoff)
                    continue
                if resp.status_code >= 400:
                    self.stats["errors"] += 1
                    return Response(resp.url, resp.status_code, resp.text)

                if cache_path:
                    cache_path.write_text(resp.text, encoding="utf-8")
                return Response(resp.url, resp.status_code, resp.text)

            time.sleep(2 ** attempt)

        self.stats["errors"] += 1
        raise FetchError(f"giving up on {url} after "
                         f"{self.config.max_retries} attempts: {last_error}")

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
