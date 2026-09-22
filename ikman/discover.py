"""Probe the live site and report its actual structure.

Run this first. It resolves the district slug and URL template, reports which
extraction strategy works and what robots.txt permits, harvests the real
category slugs, and writes the findings into the config the crawler reads.
Everything the offline build had to guess is settled here by observation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json
import logging
import re

from bs4 import BeautifulSoup

from .config import CrawlConfig, DISTRICT_SLUG_CANDIDATES, CATEGORY_SEEDS
from .extractors import (
    AD_HREF_RE, StateBlobExtractor, all_extractors, extract_search_page,
    find_next_page,
)
from .fetcher import Fetcher, RobotsDisallowed, FetchError

log = logging.getLogger("ikman.discover")

PATH_TEMPLATES = [
    ("/{locale}/ads/{location}", "/{locale}/ads/{location}/{category}"),
    ("/{locale}/ads/sri-lanka/{location}", "/{locale}/ads/{location}/{category}"),
    ("/{locale}/{location}/ads", "/{locale}/{location}/ads/{category}"),
    ("/{locale}/ads?location={location}", "/{locale}/ads?location={location}&category={category}"),
]


def _probe_search_pages(fetcher: Fetcher, config: CrawlConfig) -> dict[str, Any]:
    """Try each (district slug x path template) pair; keep the best-yielding one."""
    attempts: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None

    for slug in DISTRICT_SLUG_CANDIDATES:
        for search_tpl, category_tpl in PATH_TEMPLATES:
            trial = CrawlConfig(
                base_url=config.base_url, locale=config.locale, district_slug=slug,
                search_path_template=search_tpl, category_path_template=category_tpl,
                obey_robots=config.obey_robots, delay_seconds=config.delay_seconds,
                user_agent=config.user_agent,
            )
            url = trial.search_url()
            record: dict[str, Any] = {"url": url, "slug": slug,
                                      "search_template": search_tpl}
            try:
                resp = fetcher.get(url, use_cache=False)
            except RobotsDisallowed as exc:
                record.update(status="robots-disallowed", detail=str(exc))
                attempts.append(record)
                continue
            except FetchError as exc:
                record.update(status="fetch-error", detail=str(exc))
                attempts.append(record)
                continue

            listings, strategy = extract_search_page(resp.text, url)
            record.update(status=resp.status, listings=len(listings),
                          strategy=strategy, final_url=resp.url,
                          html_bytes=len(resp.text))
            attempts.append(record)

            if resp.status == 200 and listings:
                candidate = {
                    "slug": slug, "search_template": search_tpl,
                    "category_template": category_tpl, "url": url,
                    "listings": len(listings), "strategy": strategy,
                    "sample": [
                        {k: v for k, v in listing.to_dict().items()
                         if k in ("url", "title", "price_text", "location_text",
                                  "posted_text")}
                        for listing in listings[:3]
                    ],
                    "next_page": find_next_page(resp.text, url, config.page_param),
                    "html": resp.text,
                }
                if best is None or candidate["listings"] > best["listings"]:
                    best = candidate

    return {"attempts": attempts, "best": best}


def _probe_strategies(html: str, url: str) -> list[dict[str, Any]]:
    out = []
    for extractor in all_extractors():
        try:
            listings = extractor.search_page(html, url)
            out.append({"strategy": extractor.name, "listings": len(listings)})
        except Exception as exc:                      # noqa: BLE001 - diagnostic only
            out.append({"strategy": extractor.name, "error": repr(exc)})
    return out


def _probe_state_blob(html: str) -> dict[str, Any]:
    blobs = StateBlobExtractor().blobs(html)
    if not blobs:
        return {"found": False,
                "hint": "no hydration payload matched; parsing falls back to HTML"}
    top_keys: list[str] = []
    for blob in blobs:
        if isinstance(blob, dict):
            top_keys.extend(blob.keys())
    return {"found": True, "blob_count": len(blobs), "top_level_keys": top_keys[:40]}


# CSS-module class names carry a build hash ("normal-ad--1Vc3D") that changes on
# every deploy, so a learned selector must match on the stable stem only.
_CLASS_HASH_RE = re.compile(r"(--|___?)[A-Za-z0-9_-]{4,}$")


def _stable_class(cls: str) -> str:
    stem = _CLASS_HASH_RE.sub("", cls)
    return stem or cls


def _learn_selectors(html: str) -> dict[str, Any]:
    """Infer the card container by finding the class shared by advert anchors' ancestors."""
    soup = BeautifulSoup(html, "html.parser")
    counter: Counter[str] = Counter()

    for anchor in soup.find_all("a", href=True):
        if not AD_HREF_RE.match(anchor["href"].split("?")[0]):
            continue
        node = anchor
        for _ in range(5):
            node = node.parent
            if node is None or not getattr(node, "name", None):
                break
            for cls in (node.get("class") or []):
                counter[f"{node.name}.{cls}"] += 1

    learned: dict[str, Any] = {}
    if counter:
        # The most repeated ancestor class across adverts is the card wrapper.
        candidates = []
        for sel, n in counter.most_common(8):
            tag, cls = sel.split(".", 1)
            candidates.append({
                "selector": f"{tag}[class*='{_stable_class(cls)}']",
                "raw_class": cls,
                "matches": n,
            })
        learned["card_candidates"] = candidates
        learned["card"] = candidates[0]["selector"]
    return learned


def _probe_categories(fetcher: Fetcher, config: CrawlConfig,
                      html: str) -> dict[str, Any]:
    """Harvest real category slugs from the page's own links, seeds as backup."""
    soup = BeautifulSoup(html, "html.parser")
    slugs: Counter[str] = Counter()
    pattern = re.compile(
        rf"/{re.escape(config.locale)}/ads/(?:[a-z0-9-]+/)?([a-z0-9-]+)/?$"
    )

    for anchor in soup.find_all("a", href=True):
        path = urlparse(anchor["href"]).path
        match = pattern.match(path)
        if not match:
            continue
        slug = match.group(1)
        if slug in DISTRICT_SLUG_CANDIDATES or slug in ("ads", config.locale):
            continue
        slugs[slug] += 1

    discovered = [s for s, _ in slugs.most_common(60)]
    return {
        "discovered": discovered,
        "seeds": CATEGORY_SEEDS,
        "merged": discovered or CATEGORY_SEEDS,
    }


def run_discovery(config: CrawlConfig | None = None,
                  report_path: str | Path = "discover-report.json",
                  config_path: str | Path = "data/config.json",
                  cache_dir: str | None = None) -> dict[str, Any]:
    config = config or CrawlConfig()
    report: dict[str, Any] = {"base_url": config.base_url, "locale": config.locale}

    with Fetcher(config, cache_dir=cache_dir) as fetcher:
        origin = config.base_url
        allowed = fetcher.robots.allows(f"{origin}/en/ads/ratnapura",
                                        config.user_agent)
        report["robots"] = {
            "obeying": config.obey_robots,
            "search_path_allowed": allowed,
            "crawl_delay": fetcher.robots.crawl_delay,
        }
        if config.obey_robots and not allowed:
            report["conclusion"] = (
                "robots.txt disallows the search path for this user agent, or "
                "robots.txt could not be read. Nothing was crawled. Review "
                f"{origin}/robots.txt and the site terms before continuing."
            )
            Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

        probe = _probe_search_pages(fetcher, config)
        report["attempts"] = probe["attempts"]
        best = probe["best"]

        if not best:
            report["conclusion"] = (
                "No candidate URL returned parseable listings. Check the "
                "'attempts' list for status codes: 403/429 means the site "
                "refused the request, 200 with 0 listings means the page is "
                "rendered client-side and needs the --browser fallback."
            )
            Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

        html = best.pop("html")
        report["resolved"] = best
        report["strategies"] = _probe_strategies(html, best["url"])
        report["state_blob"] = _probe_state_blob(html)
        report["learned_selectors"] = _learn_selectors(html)
        report["categories"] = _probe_categories(fetcher, config, html)

        config.district_slug = best["slug"]
        config.search_path_template = best["search_template"]
        config.category_path_template = best["category_template"]
        config.categories = report["categories"]["merged"]
        if fetcher.robots.crawl_delay:
            config.delay_seconds = max(config.delay_seconds,
                                       fetcher.robots.crawl_delay)
        learned = report["learned_selectors"]
        if learned.get("card"):
            config.learned_selectors = {"card": learned["card"]}

        config.save(config_path)
        report["config_written_to"] = str(config_path)
        report["config"] = asdict(config)
        report["conclusion"] = (
            f"Resolved district slug '{best['slug']}' via template "
            f"'{best['search_template']}'. Strategy '{best['strategy']}' returned "
            f"{best['listings']} listings on page 1. "
            f"{len(config.categories)} categories queued. Ready to crawl."
        )

    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
