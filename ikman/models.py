"""The record we extract. One row per ikman advert."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import re


def _slug_id(url: str) -> str:
    """Stable id for an advert, derived from its canonical URL path.

    ikman ad URLs end in a slug with a trailing token, e.g.
    /en/ad/toyota-axio-2015-for-sale-ratnapura-1a2b3c4d. We key on the whole
    path so the id stays stable even when the numeric/hash token format shifts.
    """
    path = re.sub(r"^https?://[^/]+", "", url.split("?")[0]).rstrip("/")
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


@dataclass
class Listing:
    url: str
    title: str | None = None
    price_text: str | None = None
    price_value: float | None = None
    currency: str | None = None
    price_qualifier: str | None = None       # e.g. "Negotiable", "Per month"
    category: str | None = None
    subcategory: str | None = None
    location_text: str | None = None
    town: str | None = None
    district: str | None = None
    description: str | None = None
    condition: str | None = None
    seller_name: str | None = None
    seller_type: str | None = None          # member / business, when shown
    is_promoted: bool = False
    posted_text: str | None = None          # "2 days ago", "Yesterday"
    posted_at: str | None = None            # ISO-8601 once normalised
    image_urls: list[str] = field(default_factory=list)
    # Category-specific facets (mileage, bedrooms, brand, ...) kept as-is so we
    # never lose a field just because we did not anticipate it.
    attributes: dict[str, Any] = field(default_factory=dict)

    source_page: str | None = None          # SERP URL this was found on
    extracted_by: str | None = None         # which parser strategy won
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def listing_id(self) -> str:
        return _slug_id(self.url)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["listing_id"] = self.listing_id
        return d

    def to_row(self) -> dict[str, Any]:
        """Flat representation for SQLite/CSV: nested fields become JSON text."""
        d = self.to_dict()
        d["image_urls"] = json.dumps(d["image_urls"], ensure_ascii=False)
        d["attributes"] = json.dumps(d["attributes"], ensure_ascii=False)
        return d

    def merge(self, other: "Listing") -> "Listing":
        """Overlay non-empty fields from `other` (a detail-page parse) onto self."""
        for key, value in other.to_dict().items():
            if key in ("listing_id", "scraped_at"):
                continue
            if value in (None, "", [], {}, False) and key != "is_promoted":
                continue
            if key == "attributes":
                self.attributes = {**self.attributes, **value}
            elif key == "image_urls":
                seen = set(self.image_urls)
                self.image_urls += [u for u in value if u not in seen]
            else:
                setattr(self, key, value)
        return self


ROW_COLUMNS = [
    "listing_id", "url", "title", "price_text", "price_value", "currency",
    "price_qualifier", "category", "subcategory", "location_text", "town",
    "district", "description", "condition", "seller_name", "seller_type",
    "is_promoted", "posted_text", "posted_at", "image_urls", "attributes",
    "source_page", "extracted_by", "scraped_at",
]
