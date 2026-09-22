"""End-to-end crawl against an in-memory fake site (no network)."""
from __future__ import annotations

import re

import pytest

from ikman.config import CrawlConfig
from ikman.crawl import Crawler, Query, build_frontier, expand_query, slugify
from ikman.fetcher import Response
from ikman.store import Store


def serp(ad_ids: list[str], next_page: str | None) -> str:
    cards = "".join(
        f'''<li class="gtm-normal-ad">
              <a class="card-link" href="/en/ad/{ad}" title="Ad {ad}">
                <h2 class="title">Ad {ad}</h2>
                <div class="price">Rs {1000 + i * 10:,}</div>
                <div class="description">Pelmadulla, Ratnapura</div>
                <div class="updated-time">2 days ago</div>
              </a></li>'''
        for i, ad in enumerate(ad_ids)
    )
    pager = f'<link rel="next" href="{next_page}">' if next_page else ""
    return f"<html><head>{pager}</head><body><ul>{cards}</ul></body></html>"


def detail(ad: str) -> str:
    return f'''<html><body>
      <nav class="breadcrumb"><a href="/en">ikman</a><a href="/x">Vehicles</a><a href="/y">Cars</a></nav>
      <h1 class="title">Ad {ad}</h1>
      <div class="price">Rs 1,000</div>
      <dl><dt>Brand</dt><dd>Toyota</dd><dt>Condition</dt><dd>Used</dd></dl>
      <div class="description">Full description for {ad}.</div>
      <div class="gallery"><img src="/img/{ad}.jpg"></div>
    </body></html>'''


class FakeFetcher:
    """Serves a two-page SERP per query plus a detail page per advert."""

    PAGES_PER_QUERY = 2
    ADS_PER_PAGE = 3

    def __init__(self, pages_per_query: int | None = None):
        self.pages_per_query = pages_per_query or self.PAGES_PER_QUERY
        self.requested: list[str] = []
        self.stats = {"requests": 0}

    def _page_of(self, url: str) -> int:
        m = re.search(r"[?&]page=(\d+)", url)
        return int(m.group(1)) if m else 1

    def _query_key(self, url: str) -> str:
        return re.sub(r"[?&]page=\d+", "", url)

    def get(self, url: str, use_cache: bool = True) -> Response:
        self.requested.append(url)
        self.stats["requests"] += 1

        if "/ad/" in url:
            ad = url.rstrip("/").rsplit("/", 1)[-1]
            return Response(url, 200, detail(ad))

        page = self._page_of(url)
        key = self._query_key(url)
        slug = re.sub(r"[^a-z0-9]+", "", key.split("/ads/")[-1])[:16]
        ads = [f"{slug}-p{page}-{i}" for i in range(self.ADS_PER_PAGE)]
        next_page = (f"{key}?page={page + 1}"
                     if page < self.pages_per_query else None)
        return Response(url, 200, serp(ads, next_page))

    def close(self) -> None:
        pass


@pytest.fixture
def config():
    return CrawlConfig(
        categories=["vehicles", "property"],
        towns=["Ratnapura", "Balangoda"],
        delay_seconds=0,
        delay_jitter=0,
        max_pages_per_query=5,
    )


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "t.sqlite") as s:
        yield s


def test_frontier_covers_district_and_every_category(config):
    labels = [q.label for q in build_frontier(config)]
    assert labels == ["ratnapura/all", "ratnapura/vehicles", "ratnapura/property"]


def test_expansion_covers_every_town(config):
    labels = [q.label for q in expand_query(config, Query("ratnapura", "vehicles"))]
    assert labels == ["ratnapura/vehicles", "balangoda/vehicles"]


def test_slugify():
    assert slugify("Balangoda Town") == "balangoda-town"
    assert slugify("Ratnapura") == "ratnapura"


def test_crawl_paginates_and_stores_listings(config, store):
    fetcher = FakeFetcher()
    crawler = Crawler(config, store, fetcher, progress=lambda m: None)
    crawler.crawl_search()

    # 3 queries x 2 pages x 3 ads, all distinct per query
    assert crawler.stats.pages == 6
    assert store.count() == 18
    assert crawler.stats.listings_new == 18

    listing = next(store.iter_listings())
    assert listing.town == "Pelmadulla"
    assert listing.district == "Ratnapura"
    assert listing.price_value is not None


def test_query_category_fills_in_when_card_omits_it(config, store):
    crawler = Crawler(config, store, FakeFetcher(), progress=lambda m: None)
    crawler.crawl_query(Query("ratnapura", "vehicles"))
    assert all(l.category == "vehicles" for l in store.iter_listings())


def test_saturated_query_fans_out_to_towns(config, store):
    """A query that runs to the page cap is re-asked per town."""
    config.max_pages_per_query = 2
    fetcher = FakeFetcher(pages_per_query=50)     # never runs out of pages
    crawler = Crawler(config, store, fetcher, progress=lambda m: None)
    crawler.crawl_search()

    assert crawler.stats.expanded, "expected at least one category to fan out"
    assert "ratnapura/vehicles" in crawler.stats.expanded
    assert any("balangoda" in url for url in fetcher.requested)


def test_narrow_query_is_not_expanded(config, store):
    """Queries that finish before the cap must not trigger a town fan-out."""
    crawler = Crawler(config, store, FakeFetcher(pages_per_query=1),
                      progress=lambda m: None)
    crawler.crawl_search()
    assert crawler.stats.expanded == []


def test_resume_skips_pages_already_visited(config, store):
    first = FakeFetcher()
    Crawler(config, store, first, progress=lambda m: None).crawl_search()
    before = store.count()

    second = FakeFetcher()
    crawler = Crawler(config, store, second, progress=lambda m: None)
    crawler.crawl_search()

    assert second.requested == [], "second run should hit no SERP pages"
    assert store.count() == before


def test_detail_crawl_enriches_listings(config, store):
    fetcher = FakeFetcher()
    crawler = Crawler(config, store, fetcher, progress=lambda m: None)
    crawler.crawl_query(Query("ratnapura", "vehicles"))

    assert store.pending_details(), "listings should start without detail"
    crawler.crawl_details()

    assert store.pending_details() == []
    enriched = next(store.iter_listings())
    assert enriched.description.startswith("Full description")
    assert enriched.attributes["Brand"] == "Toyota"
    assert enriched.condition == "Used"
    assert enriched.image_urls
    # Detail merge must not discard what the search card knew.
    assert enriched.town == "Pelmadulla"
    assert enriched.posted_text == "2 days ago"


def test_detail_crawl_is_idempotent(config, store):
    crawler = Crawler(config, store, FakeFetcher(), progress=lambda m: None)
    crawler.crawl_query(Query("ratnapura", "vehicles"))
    crawler.crawl_details()
    count = store.count()
    crawler.crawl_details()
    assert store.count() == count


def test_max_listings_budget_stops_the_crawl(config, store):
    config.max_listings = 4
    crawler = Crawler(config, store, FakeFetcher(), progress=lambda m: None)
    crawler.crawl_search()
    # Stops at the first page boundary at or past the budget.
    assert 4 <= store.count() <= 6


def test_missing_advert_is_not_retried_forever(config, store):
    class GoneFetcher(FakeFetcher):
        def get(self, url, use_cache=True):
            if "/ad/" in url:
                return Response(url, 410, "gone")
            return super().get(url)

    crawler = Crawler(config, store, GoneFetcher(), progress=lambda m: None)
    crawler.crawl_query(Query("ratnapura", "vehicles"))
    crawler.crawl_details()
    assert store.pending_details() == []


def test_server_error_on_serp_does_not_abort_whole_crawl(config, store):
    class FlakyFetcher(FakeFetcher):
        def get(self, url, use_cache=True):
            if "property" in url:
                return Response(url, 503, "unavailable")
            return super().get(url)

    crawler = Crawler(config, store, FlakyFetcher(), progress=lambda m: None)
    crawler.crawl_search()
    assert crawler.stats.errors >= 1
    assert store.count() > 0, "other categories should still be collected"
