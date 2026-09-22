"""Static configuration: site URLs, the Ratnapura locality list and category tree.

Slugs that could not be verified against the live site are listed as *candidates*
rather than constants. ``ikman discover`` probes them and writes the winners to
the runtime config, so a slug change upstream is a one-command fix instead of a
code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import json

BASE_URL = "https://ikman.lk"
DEFAULT_LOCALE = "en"

# Ratnapura District, Sabaragamuwa Province. ikman exposes the district as one
# location facet and each town below it as a child facet.
DISTRICT_NAME = "Ratnapura"

# CONFIRMED from live URLs: the district facet is the bare slug "ratnapura",
# e.g. https://ikman.lk/en/ads/ratnapura/land-for-sale
DISTRICT_SLUG_CANDIDATES = [
    "ratnapura",
    "ratnapura-district",
    "rathnapura",
    "ratnapura-sri-lanka",
]

# Town facets are bare slugs too (.../ads/eheliyagoda/land-for-sale), but a
# *city* facet inside a district carries a numeric id ("ratnapura-91" is
# Ratnapura City, "kurunegala-61" is Kurunegala City). The ids are not derivable
# from the name, so `discover` has to read them off the location filter; a bare
# slugified town is tried first and the numeric form only comes from discovery.
CITY_SLUG_PATTERN = r"^[a-z0-9-]+-\d+$"

# Town slugs seen in live URLs. Others are slugified from RATNAPURA_TOWNS.
VERIFIED_TOWN_SLUGS = {
    "Ratnapura": "ratnapura",
    "Eheliyagoda": "eheliyagoda",
    "Balangoda": "balangoda",
    "Pelmadulla": "pelmadulla",
    "Kuruwita": "kuruwita",
}

# Advert counts read off live category pages, for sanity-checking a crawl's
# coverage. Approximate and they drift, but an order of magnitude below these
# means the crawl is truncating.
KNOWN_LISTING_COUNTS = {
    "ratnapura/land-for-sale": 235,
    "ratnapura-91/land-for-sale": 66,      # Ratnapura City
    "eheliyagoda/land-for-sale": 72,
    "kuruwita/land-for-sale": 19,
}

# Towns / localities within Ratnapura District. Used to fan the crawl out so no
# single query hits the site's pagination ceiling (see crawl.build_frontier).
RATNAPURA_TOWNS = [
    "Ratnapura", "Embilipitiya", "Balangoda", "Pelmadulla", "Eheliyagoda",
    "Kuruwita", "Kalawana", "Nivithigala", "Rakwana", "Kahawatta",
    "Opanayaka", "Godakawela", "Weligepola", "Ayagama", "Elapatha",
    "Imbulpe", "Kolonna", "Kiriella", "Panadugama", "Kalthota",
    "Udawalawe", "Thanamalwila", "Balangoda Town", "Karawita", "Gillimale",
]

# Top-level ikman categories. Children are discovered from the live category
# nav; these seeds guarantee coverage even if discovery of the nav fails.
# "land-for-sale" and "property" are confirmed from live URLs; the rest are
# seeds that `discover` replaces with the real category nav.
CATEGORY_SEEDS = [
    "land-for-sale",
    "property",
    "vehicles",
    "electronics",
    "home-garden",
    "animals",
    "business-industry",
    "essentials",
    "jobs",
    "services",
    "education",
    "hobby-sport-kids",
    "agriculture",
]


@dataclass
class CrawlConfig:
    """Runtime knobs. Persisted to disk by `discover` and read by `crawl`."""

    base_url: str = BASE_URL
    locale: str = DEFAULT_LOCALE
    district_slug: str = DISTRICT_SLUG_CANDIDATES[0]

    # URL template resolved by discovery. {locale}/{location}/{category}/{page}
    search_path_template: str = "/{locale}/ads/{location}"
    category_path_template: str = "/{locale}/ads/{location}/{category}"
    page_param: str = "page"

    # Politeness. Defaults are deliberately conservative: roughly one request
    # per 1.5s with jitter, single-threaded.
    delay_seconds: float = 1.5
    delay_jitter: float = 0.75
    max_retries: int = 4
    timeout_seconds: float = 30.0
    concurrency: int = 1

    # Safety rails
    obey_robots: bool = True
    # A live URL was observed at ?page=41 for the district-wide query, so the
    # cap has to sit above that or the crawl truncates without saying so.
    max_pages_per_query: int = 60
    max_listings: int | None = None
    user_agent: str = (
        "ikman-ratnapura-extractor/0.1 (+https://github.com/KDDilshan/"
        "rathnpura-dta-exractor) research/data-collection"
    )

    # What to collect
    fetch_detail_pages: bool = True
    collect_images: bool = True
    categories: list[str] = field(default_factory=lambda: list(CATEGORY_SEEDS))
    towns: list[str] = field(default_factory=lambda: list(RATNAPURA_TOWNS))

    # Selectors learned by `discover`; empty means "use built-in heuristics".
    learned_selectors: dict[str, Any] = field(default_factory=dict)

    @property
    def request_interval(self) -> float:
        return self.delay_seconds

    def search_url(self, category: str | None = None, page: int = 1) -> str:
        loc = self.district_slug
        if category:
            path = self.category_path_template.format(
                locale=self.locale, location=loc, category=category
            )
        else:
            path = self.search_path_template.format(locale=self.locale, location=loc)
        url = f"{self.base_url.rstrip('/')}{path}"
        if page > 1:
            url = f"{url}?{self.page_param}={page}"
        return url

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CrawlConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


DEFAULT_CONFIG_PATH = Path("data/config.json")
