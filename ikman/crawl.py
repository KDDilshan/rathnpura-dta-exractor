"""Crawl orchestration.

Search-result pagination on classifieds sites is capped (ikman stops well short
of showing every match for a broad query), so asking once for "everything in
Ratnapura" silently truncates. The crawler therefore works a frontier of
(location, category) queries and, when a query *saturates* - it runs to the page
cap and still finds new adverts - it fans that category out across the district's
towns to reach the listings the capped query hid. Narrow queries are never
expanded, so the request budget stays proportional to how much data exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable
import logging
import re

from .config import CrawlConfig
from .extractors import extract_detail_page, extract_search_page, find_next_page
from .fetcher import Fetcher, FetchError, RobotsDisallowed
from .models import Listing
from .store import Store

log = logging.getLogger("ikman.crawl")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@dataclass
class Query:
    location: str
    category: str | None = None
    label: str = ""

    def __post_init__(self) -> None:
        self.label = f"{self.location}/{self.category or 'all'}"


@dataclass
class CrawlStats:
    queries: int = 0
    pages: int = 0
    listings_new: int = 0
    listings_seen: int = 0
    details: int = 0
    errors: int = 0
    saturated: list[str] = field(default_factory=list)
    expanded: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.queries} queries, {self.pages} pages, "
            f"{self.listings_new} new listings ({self.listings_seen} seen), "
            f"{self.details} detail pages, {self.errors} errors"
        )


def build_frontier(config: CrawlConfig) -> list[Query]:
    """Tier 1: the whole district, then district-wide per category."""
    frontier = [Query(config.district_slug)]
    frontier += [Query(config.district_slug, cat) for cat in config.categories]
    return frontier


def expand_query(config: CrawlConfig, query: Query) -> list[Query]:
    """Tier 2: re-ask a saturated category town by town."""
    return [Query(slugify(town), query.category) for town in config.towns]


class Crawler:
    def __init__(self, config: CrawlConfig, store: Store, fetcher: Fetcher,
                 progress: Callable[[str], None] | None = None):
        self.config = config
        self.store = store
        self.fetcher = fetcher
        self.stats = CrawlStats()
        self._progress = progress or (lambda msg: log.info(msg))

    def _query_url(self, query: Query, page: int = 1) -> str:
        trial = CrawlConfig(
            base_url=self.config.base_url, locale=self.config.locale,
            district_slug=query.location,
            search_path_template=self.config.search_path_template,
            category_path_template=self.config.category_path_template,
            page_param=self.config.page_param,
        )
        return trial.search_url(query.category, page)

    def crawl_query(self, query: Query) -> tuple[int, bool]:
        """Page through one query. -> (new listings, saturated).

        Saturated means we stopped because of the page cap while still finding
        adverts, i.e. the site is very likely withholding more.
        """
        self.stats.queries += 1
        new_total = 0
        url = self._query_url(query)
        page = 1
        hit_cap = False
        found_on_last_page = 0

        while url and page <= self.config.max_pages_per_query:
            if self.store.visited(url):
                # Follow the successor recorded on the previous run instead of
                # guessing page numbers; no successor means the query ended here.
                self._progress(f"  skip (already visited) {url}")
                next_url = self.store.next_page_of(url)
                if not next_url:
                    return new_total, False
                url = next_url
                page += 1
                continue

            try:
                resp = self.fetcher.get(url)
            except RobotsDisallowed as exc:
                self.store.record_page(url, "serp", 0, error=str(exc))
                self._progress(f"  robots blocked {url}")
                break
            except FetchError as exc:
                self.stats.errors += 1
                self.store.record_page(url, "serp", 0, error=str(exc))
                self._progress(f"  error {url}: {exc}")
                break

            if resp.status >= 400:
                self.stats.errors += 1
                self.store.record_page(url, "serp", resp.status)
                self._progress(f"  HTTP {resp.status} {url}")
                break

            listings, strategy = extract_search_page(
                resp.text, url, self.config.learned_selectors
            )
            listings = [self._tag(listing, query) for listing in listings]
            new, seen = self.store.upsert_many(listings)
            new_total += new
            found_on_last_page = len(listings)
            next_url = find_next_page(resp.text, url, self.config.page_param)

            self.stats.pages += 1
            self.stats.listings_new += new
            self.stats.listings_seen += seen
            self.store.record_page(url, "serp", resp.status, len(listings),
                                   strategy, next_url=next_url)
            self._progress(
                f"  p{page} [{strategy}] {len(listings)} listings ({new} new) {url}"
            )

            if not listings:
                break
            if self._budget_reached():
                return new_total, False

            url = next_url
            page += 1

        if page > self.config.max_pages_per_query and found_on_last_page:
            hit_cap = True
        return new_total, hit_cap

    def _tag(self, listing: Listing, query: Query) -> Listing:
        """Attach the query's category as a fallback when the card omits it."""
        if not listing.category and query.category:
            listing.category = query.category
        if not listing.district:
            listing.district = "Ratnapura"
        return listing

    def _budget_reached(self) -> bool:
        limit = self.config.max_listings
        return bool(limit and self.store.count() >= limit)

    def crawl_search(self) -> None:
        frontier = build_frontier(self.config)
        queued = {q.label for q in frontier}

        while frontier:
            if self._budget_reached():
                self._progress(f"listing budget {self.config.max_listings} reached")
                return
            query = frontier.pop(0)
            self._progress(f"query {query.label}")
            _, saturated = self.crawl_query(query)

            if saturated and query.category and query.location == self.config.district_slug:
                self.stats.saturated.append(query.label)
                expansions = [q for q in expand_query(self.config, query)
                              if q.label not in queued]
                queued.update(q.label for q in expansions)
                frontier.extend(expansions)
                self.stats.expanded.append(query.label)
                self._progress(
                    f"  '{query.label}' hit the {self.config.max_pages_per_query}-page "
                    f"cap; fanning out to {len(expansions)} towns"
                )

    def crawl_details(self, urls: Iterable[str] | None = None) -> None:
        pending = list(urls) if urls is not None else self.store.pending_details()
        total = len(pending)
        self._progress(f"fetching {total} detail pages")

        for index, url in enumerate(pending, 1):
            if self._budget_reached():
                return
            try:
                resp = self.fetcher.get(url)
            except RobotsDisallowed as exc:
                self.store.record_page(url, "detail", 0, error=str(exc))
                continue
            except FetchError as exc:
                self.stats.errors += 1
                self.store.record_page(url, "detail", 0, error=str(exc))
                continue

            if resp.status >= 400:
                self.stats.errors += 1
                self.store.record_page(url, "detail", resp.status)
                # A 404/410 means the advert is gone; stop retrying it.
                if resp.status in (404, 410):
                    self.store.mark_detail_fetched(url)
                continue

            listing = extract_detail_page(resp.text, url,
                                          self.config.learned_selectors)
            if listing:
                if not self.config.collect_images:
                    listing.image_urls = []
                self.store.upsert(listing, detail_fetched=True)
                self.stats.details += 1
            self.store.mark_detail_fetched(url)
            self.store.record_page(url, "detail", resp.status,
                                   1 if listing else 0,
                                   listing.extracted_by if listing else None)
            if index % 25 == 0 or index == total:
                self._progress(f"  details {index}/{total}")

    def run(self) -> CrawlStats:
        run_id = self.store.start_run(
            {"district": self.config.district_slug,
             "categories": self.config.categories}
        )
        try:
            self.crawl_search()
            if self.config.fetch_detail_pages:
                self.crawl_details()
        finally:
            self.store.end_run(run_id, self.stats.summary())
        return self.stats
