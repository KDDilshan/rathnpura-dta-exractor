"""Layered extraction strategies for ikman search-result and detail pages.

The live site could not be inspected while this was written, so nothing here
depends on a single hardcoded selector. Four strategies run in order of
reliability and the crawler keeps whichever yields the most listings for a
given page:

1. ``JsonLdExtractor``    - schema.org blocks in <script type=application/ld+json>
2. ``StateBlobExtractor`` - the hydration payload a JS app embeds in the HTML
3. ``SelectorExtractor``  - candidate CSS selector sets, incl. any learned by `discover`
4. ``LinkHeuristicExtractor`` - find advert anchors by URL shape, read their card

Strategy 4 is the safety net: as long as advert URLs keep the /<locale>/ad/<slug>
shape, it returns rows even if every class name on the site changes.
"""
from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
import json
import re

from bs4 import BeautifulSoup

from .models import Listing
from .parsing import clean, parse_posted, parse_price, split_location

# /en/ad/<slug>, /si/ad/<slug>, /ta/ad/<slug>
AD_HREF_RE = re.compile(r"^/(?:en|si|ta)/ad/[^/?#]+/?$")

_STATE_BLOB_PATTERNS = [
    re.compile(r"window\.initialData\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S),
    re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S),
    re.compile(r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S),
    re.compile(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', re.S),
    re.compile(r"window\.__data\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S),
]

_PRICE_HINT_RE = re.compile(r"(?:Rs\.?|LKR|රු)\s*[\d,]+|^\s*Free\s*$", re.IGNORECASE)
_DATE_HINT_RE = re.compile(
    r"\b(?:\d+\s*(?:second|minute|min|hour|hr|day|week|month|year)s?\s+ago"
    r"|today|yesterday|just now)\b",
    re.IGNORECASE,
)


def _soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _abs_url(href: str, base: str) -> str:
    return urljoin(base, href)


def _is_ad_url(url: str) -> bool:
    return bool(AD_HREF_RE.match(urlparse(url).path))


def _walk(node: Any) -> Iterable[Any]:
    """Depth-first walk over nested dict/list JSON."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


class Extractor:
    name = "base"

    def search_page(self, html: str, page_url: str) -> list[Listing]:
        raise NotImplementedError

    def detail_page(self, html: str, page_url: str) -> Listing | None:
        return None


class JsonLdExtractor(Extractor):
    """schema.org Product/Offer/ItemList markup, the most stable source when present."""

    name = "json-ld"

    def _blocks(self, html: str) -> list[Any]:
        out = []
        for script in _soup(html).find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text() or ""
            try:
                out.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                # Some sites emit several concatenated objects in one block.
                for chunk in re.findall(r"\{.*?\}(?=\s*[\{,]|\s*$)", raw, re.S):
                    try:
                        out.append(json.loads(chunk))
                    except json.JSONDecodeError:
                        continue
        return out

    def _from_product(self, obj: dict, page_url: str) -> Listing | None:
        url = obj.get("url") or obj.get("@id") or ""
        if url:
            url = _abs_url(url, page_url)
        if not url or not _is_ad_url(url):
            return None

        offers = obj.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        price_text = None
        value = None
        currency = offers.get("priceCurrency") if isinstance(offers, dict) else None
        if isinstance(offers, dict) and offers.get("price") is not None:
            price_text = f"{currency or ''} {offers['price']}".strip()
            try:
                value = float(str(offers["price"]).replace(",", ""))
            except (TypeError, ValueError):
                value = None

        images = obj.get("image") or []
        if isinstance(images, str):
            images = [images]
        images = [_abs_url(i, page_url) for i in images if isinstance(i, str)]

        area = obj.get("areaServed") or obj.get("availableAtOrFrom") or {}
        loc_text = None
        if isinstance(area, dict):
            loc_text = area.get("name") or (area.get("address") or {}).get(
                "addressLocality"
            ) if isinstance(area.get("address"), dict) else area.get("name")
        elif isinstance(area, str):
            loc_text = area
        town, district = split_location(loc_text)

        return Listing(
            url=url,
            title=clean(obj.get("name")),
            price_text=price_text,
            price_value=value,
            currency=currency,
            category=clean(obj.get("category")),
            description=clean(obj.get("description")),
            condition=clean(
                (offers.get("itemCondition") if isinstance(offers, dict) else None)
                or obj.get("itemCondition")
            ),
            location_text=clean(loc_text),
            town=town,
            district=district,
            image_urls=images,
            source_page=page_url,
            extracted_by=self.name,
        )

    def search_page(self, html: str, page_url: str) -> list[Listing]:
        found: dict[str, Listing] = {}
        for block in self._blocks(html):
            for node in _walk(block):
                ntype = node.get("@type")
                types = ntype if isinstance(ntype, list) else [ntype]
                if not any(t in ("Product", "Offer", "Vehicle", "Residence",
                                 "Car", "House", "Apartment", "JobPosting")
                           for t in types if t):
                    continue
                listing = self._from_product(node, page_url)
                if listing:
                    found.setdefault(listing.url, listing)
        return list(found.values())

    def detail_page(self, html: str, page_url: str) -> Listing | None:
        for block in self._blocks(html):
            for node in _walk(block):
                ntype = node.get("@type")
                types = ntype if isinstance(ntype, list) else [ntype]
                if not any(t for t in types if t in (
                    "Product", "Vehicle", "Car", "House", "Apartment",
                    "Residence", "JobPosting", "Offer",
                )):
                    continue
                obj = dict(node)
                obj.setdefault("url", page_url)
                listing = self._from_product(obj, page_url)
                if listing:
                    return listing
        return None


class StateBlobExtractor(Extractor):
    """The hydration payload a JS front end leaves in the HTML.

    Shapes differ between releases, so rather than pinning a path we walk the
    whole tree and treat any dict that carries an advert-shaped url/slug as a
    listing. That survives re-nesting of the payload.
    """

    name = "state-blob"

    _URL_KEYS = ("url", "href", "slug", "adUrl", "link", "permalink", "detailUrl")
    _TITLE_KEYS = ("title", "name", "adTitle", "heading", "subject")
    _PRICE_KEYS = ("price", "priceText", "displayPrice", "amount", "money", "priceLabel")
    _LOC_KEYS = ("location", "locationName", "area", "city", "town", "locality",
                 "regionName")
    _DATE_KEYS = ("timeStamp", "timestamp", "postedAt", "createdAt", "date",
                  "displayDate", "time", "age")
    _IMG_KEYS = ("image", "images", "imageUrl", "imageUrls", "thumb", "thumbnail",
                 "picture", "pictures", "media")

    def blobs(self, html: str) -> list[Any]:
        out = []
        for pattern in _STATE_BLOB_PATTERNS:
            for match in pattern.finditer(html):
                try:
                    out.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    continue
        return out

    @staticmethod
    def _first(node: dict, keys: Iterable[str]) -> Any:
        for key in keys:
            if key in node and node[key] not in (None, "", [], {}):
                return node[key]
        return None

    def _images(self, node: dict, page_url: str) -> list[str]:
        raw = self._first(node, self._IMG_KEYS)
        urls: list[str] = []

        def collect(value: Any) -> None:
            if isinstance(value, str):
                if re.search(r"\.(?:jpe?g|png|webp|avif)", value, re.IGNORECASE) or \
                        "/image" in value:
                    urls.append(_abs_url(value, page_url))
            elif isinstance(value, dict):
                for k in ("url", "src", "href", "large", "medium", "small", "original"):
                    if isinstance(value.get(k), str):
                        collect(value[k])
                        return
                for v in value.values():
                    collect(v)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(raw)
        seen: set[str] = set()
        return [u for u in urls if not (u in seen or seen.add(u))]

    def _node_to_listing(self, node: dict, page_url: str) -> Listing | None:
        raw_url = self._first(node, self._URL_KEYS)
        if not isinstance(raw_url, str):
            return None
        url = _abs_url(raw_url if raw_url.startswith(("http", "/")) else f"/en/ad/{raw_url}",
                       page_url)
        if not _is_ad_url(url):
            return None

        title = self._first(node, self._TITLE_KEYS)
        if not isinstance(title, str):
            title = None

        price_raw = self._first(node, self._PRICE_KEYS)
        price_text = None
        if isinstance(price_raw, (int, float)):
            price_text = f"Rs {price_raw:,.0f}"
        elif isinstance(price_raw, str):
            price_text = clean(price_raw)
        elif isinstance(price_raw, dict):
            amount = price_raw.get("amount", price_raw.get("value"))
            if amount is not None:
                cur = price_raw.get("currency", "Rs")
                price_text = f"{cur} {amount}"
        value, currency, qualifier = parse_price(price_text)

        loc_raw = self._first(node, self._LOC_KEYS)
        if isinstance(loc_raw, dict):
            loc_raw = loc_raw.get("name") or loc_raw.get("label")
        loc_text = clean(loc_raw) if isinstance(loc_raw, str) else None
        town, district = split_location(loc_text)

        posted_raw = self._first(node, self._DATE_KEYS)
        posted_text = clean(str(posted_raw)) if posted_raw is not None else None

        # Anything scalar we did not map is preserved rather than dropped.
        mapped = set(
            self._URL_KEYS + self._TITLE_KEYS + self._PRICE_KEYS
            + self._LOC_KEYS + self._DATE_KEYS + self._IMG_KEYS
        ) | {"description", "details", "condition", "category", "categoryName"}
        attributes = {
            k: v for k, v in node.items()
            if k not in mapped and isinstance(v, (str, int, float, bool)) and v != ""
        }

        return Listing(
            url=url,
            title=clean(title),
            price_text=price_text,
            price_value=value,
            currency=currency,
            price_qualifier=qualifier,
            category=clean(node.get("category") or node.get("categoryName")),
            description=clean(node.get("description") or node.get("details")),
            condition=clean(node.get("condition")),
            location_text=loc_text,
            town=town,
            district=district,
            is_promoted=bool(
                node.get("isPromoted") or node.get("promoted") or node.get("isFeatured")
            ),
            posted_text=posted_text,
            posted_at=parse_posted(posted_text),
            image_urls=self._images(node, page_url),
            attributes=attributes,
            source_page=page_url,
            extracted_by=self.name,
        )

    def search_page(self, html: str, page_url: str) -> list[Listing]:
        found: dict[str, Listing] = {}
        for blob in self.blobs(html):
            for node in _walk(blob):
                listing = self._node_to_listing(node, page_url)
                if listing:
                    found.setdefault(listing.url, listing)
        return list(found.values())

    def detail_page(self, html: str, page_url: str) -> Listing | None:
        best: Listing | None = None
        best_score = -1
        for blob in self.blobs(html):
            for node in _walk(blob):
                listing = self._node_to_listing(node, page_url)
                if not listing:
                    continue
                score = sum(
                    1 for v in (listing.title, listing.description, listing.price_text,
                                listing.location_text) if v
                ) + len(listing.attributes) * 0.1
                if score > best_score:
                    best, best_score = listing, score
        return best


class SelectorExtractor(Extractor):
    """Candidate CSS selector sets, plus anything `discover` learned."""

    name = "selectors"

    CARD_SELECTORS = [
        "li[class*='gtm-']",
        "li[data-testid*='ad']",
        "div[data-testid*='ad-card']",
        "li[class*='normal-ad']",
        "div[class*='ad-card']",
        "li[class*='ad-card']",
        "article[class*='ad']",
        "li.serp-item",
    ]
    TITLE_SELECTORS = ["h2", "h3", "[class*='title']", "a[class*='title']"]
    PRICE_SELECTORS = ["[class*='price']", "[data-testid*='price']"]
    # On SERP cards ikman renders the location inside a "description" element,
    # but on a detail page that class holds the advert body - so the two
    # contexts need different candidate lists.
    LOC_SELECTORS = ["[class*='location']", "[class*='description']", "[class*='area']"]
    DETAIL_LOC_SELECTORS = ["[class*='location']", "[class*='area']",
                            "[class*='address']", "[data-testid*='location']"]
    DATE_SELECTORS = ["[class*='updated']", "[class*='time']", "[class*='date']",
                      "[class*='boosted']"]

    def __init__(self, learned: dict[str, Any] | None = None):
        self.learned = learned or {}

    def _cards(self, soup: BeautifulSoup):
        selectors = ([self.learned["card"]] if self.learned.get("card") else []) \
            + self.CARD_SELECTORS
        best: list = []
        for selector in selectors:
            try:
                cards = soup.select(selector)
            except Exception:
                continue
            # A real card contains exactly one advert link; nav lists do not.
            cards = [c for c in cards
                     if any(AD_HREF_RE.match(a.get("href", "").split("?")[0])
                            for a in c.find_all("a", href=True))]
            if len(cards) > len(best):
                best = cards
        return best

    def _pick(self, card, selectors: list[str], learned_key: str) -> str | None:
        keys = ([self.learned[learned_key]] if self.learned.get(learned_key) else []) \
            + selectors
        for selector in keys:
            try:
                node = card.select_one(selector)
            except Exception:
                continue
            if node:
                text = clean(node.get_text(" "))
                if text:
                    return text
        return None

    def search_page(self, html: str, page_url: str) -> list[Listing]:
        soup = _soup(html)
        found: dict[str, Listing] = {}
        for card in self._cards(soup):
            anchor = next(
                (a for a in card.find_all("a", href=True)
                 if AD_HREF_RE.match(a["href"].split("?")[0])),
                None,
            )
            if not anchor:
                continue
            url = _abs_url(anchor["href"], page_url)

            title = self._pick(card, self.TITLE_SELECTORS, "title") \
                or clean(anchor.get_text(" ")) or clean(anchor.get("title"))
            price_text = self._pick(card, self.PRICE_SELECTORS, "price")
            loc_text = self._pick(card, self.LOC_SELECTORS, "location")
            posted_text = self._pick(card, self.DATE_SELECTORS, "date")

            value, currency, qualifier = parse_price(price_text)
            town, district = split_location(loc_text)
            images = [
                _abs_url(img.get("src") or img.get("data-src") or "", page_url)
                for img in card.find_all("img")
                if img.get("src") or img.get("data-src")
            ]

            found.setdefault(url, Listing(
                url=url,
                title=title,
                price_text=price_text,
                price_value=value,
                currency=currency,
                price_qualifier=qualifier,
                location_text=loc_text,
                town=town,
                district=district,
                posted_text=posted_text,
                posted_at=parse_posted(posted_text),
                image_urls=[i for i in images if i],
                is_promoted=bool(
                    card.select_one("[class*='promot'], [class*='feature'], "
                                    "[class*='urgent'], [class*='top-ad']")
                ),
                source_page=page_url,
                extracted_by=self.name,
            ))
        return list(found.values())

    def detail_page(self, html: str, page_url: str) -> Listing | None:
        soup = _soup(html)
        title = None
        for selector in ["h1", "[class*='title'] h1", "[data-testid*='title']"]:
            node = soup.select_one(selector)
            if node and clean(node.get_text(" ")):
                title = clean(node.get_text(" "))
                break

        price_text = self._pick(soup, self.PRICE_SELECTORS, "price")
        value, currency, qualifier = parse_price(price_text)

        description = None
        for selector in ["[class*='description']", "[data-testid*='description']",
                         "[class*='ad-description']", "#description"]:
            node = soup.select_one(selector)
            if node and clean(node.get_text(" ")):
                description = clean(node.get_text(" "))
                break

        # Detail pages render facets as definition lists or label/value rows.
        attributes: dict[str, Any] = {}
        for dl in soup.find_all("dl"):
            terms = dl.find_all("dt")
            defs = dl.find_all("dd")
            for term, definition in zip(terms, defs):
                key, val = clean(term.get_text(" ")), clean(definition.get_text(" "))
                if key and val:
                    attributes[key.rstrip(":")] = val
        for row in soup.select("[class*='attribute'], [class*='detail-item'], "
                               "[class*='spec']"):
            label = row.select_one("[class*='label'], [class*='key'], strong, b")
            val_node = row.select_one("[class*='value'], [class*='val'], span:last-child")
            if label and val_node:
                key, val = clean(label.get_text(" ")), clean(val_node.get_text(" "))
                if key and val and key != val:
                    attributes.setdefault(key.rstrip(":"), val)

        loc_text = self._pick(soup, self.DETAIL_LOC_SELECTORS, "location")
        town, district = split_location(loc_text)
        posted_text = self._pick(soup, self.DATE_SELECTORS, "date")

        breadcrumbs = [clean(a.get_text(" ")) for a in
                       soup.select("[class*='breadcrumb'] a, nav[aria-label*='readcrumb'] a")]
        breadcrumbs = [b for b in breadcrumbs if b]

        images: list[str] = []
        for img in soup.select("[class*='gallery'] img, [class*='slider'] img, "
                               "[class*='photo'] img, main img"):
            src = img.get("src") or img.get("data-src")
            if src:
                images.append(_abs_url(src, page_url))
        seen: set[str] = set()
        images = [i for i in images if not (i in seen or seen.add(i))]

        if not any([title, price_text, description, attributes]):
            return None

        return Listing(
            url=page_url,
            title=title,
            price_text=price_text,
            price_value=value,
            currency=currency,
            price_qualifier=qualifier,
            category=breadcrumbs[1] if len(breadcrumbs) > 1 else None,
            subcategory=breadcrumbs[2] if len(breadcrumbs) > 2 else None,
            description=description,
            condition=attributes.get("Condition"),
            location_text=loc_text,
            town=town,
            district=district,
            posted_text=posted_text,
            posted_at=parse_posted(posted_text),
            image_urls=images,
            attributes=attributes,
            source_page=page_url,
            extracted_by=self.name,
        )


class LinkHeuristicExtractor(Extractor):
    """Last-resort net: find advert anchors by URL shape, read their surroundings.

    Keeps working when class names change, because it keys only on the advert
    URL pattern and on text that *looks* like a price or a relative date.
    """

    name = "link-heuristic"

    def search_page(self, html: str, page_url: str) -> list[Listing]:
        soup = _soup(html)
        found: dict[str, Listing] = {}

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].split("?")[0]
            if not AD_HREF_RE.match(href):
                continue
            url = _abs_url(anchor["href"], page_url)
            if url in found:
                continue

            # Climb to the nearest ancestor that looks like a self-contained card.
            card = anchor
            for _ in range(4):
                parent = card.parent
                if parent is None or parent.name in ("body", "html", "[document]"):
                    break
                other_ads = {
                    a["href"].split("?")[0] for a in parent.find_all("a", href=True)
                    if AD_HREF_RE.match(a["href"].split("?")[0])
                }
                if len(other_ads) > 1:
                    break
                card = parent

            text_nodes = [clean(t) for t in card.stripped_strings]
            text_nodes = [t for t in text_nodes if t]

            title = clean(anchor.get("title")) or clean(anchor.get_text(" "))
            if not title:
                title = next((t for t in text_nodes if len(t) > 12), None)

            price_text = next((t for t in text_nodes if _PRICE_HINT_RE.search(t)), None)
            posted_text = next((t for t in text_nodes if _DATE_HINT_RE.search(t)), None)
            loc_text = next(
                (t for t in text_nodes
                 if any(town.lower() in t.lower() for town in ("Ratnapura", "Embilipitiya",
                        "Balangoda", "Pelmadulla", "Eheliyagoda", "Kuruwita"))
                 and t != price_text),
                None,
            )

            value, currency, qualifier = parse_price(price_text)
            town, district = split_location(loc_text)
            images = [
                _abs_url(img.get("src") or img.get("data-src") or "", page_url)
                for img in card.find_all("img")
                if img.get("src") or img.get("data-src")
            ]

            found[url] = Listing(
                url=url,
                title=title,
                price_text=price_text,
                price_value=value,
                currency=currency,
                price_qualifier=qualifier,
                location_text=loc_text,
                town=town,
                district=district,
                posted_text=posted_text,
                posted_at=parse_posted(posted_text),
                image_urls=[i for i in images if i],
                source_page=page_url,
                extracted_by=self.name,
            )
        return list(found.values())


def all_extractors(learned: dict[str, Any] | None = None) -> list[Extractor]:
    return [
        JsonLdExtractor(),
        StateBlobExtractor(),
        SelectorExtractor(learned),
        LinkHeuristicExtractor(),
    ]


def extract_search_page(
    html: str, page_url: str, learned: dict[str, Any] | None = None
) -> tuple[list[Listing], str]:
    """Run every strategy; keep the richest result set.

    Ranks by listing count first, then by how many fields came back populated,
    so a strategy that finds the same adverts with more detail wins.
    """
    best: list[Listing] = []
    best_name = "none"
    best_score = (0, 0.0)

    for extractor in all_extractors(learned):
        try:
            listings = extractor.search_page(html, page_url)
        except Exception:
            continue
        if not listings:
            continue
        filled = sum(
            1 for listing in listings
            for v in (listing.title, listing.price_text, listing.location_text,
                      listing.posted_text)
            if v
        ) / len(listings)
        score = (len(listings), filled)
        if score > best_score:
            best, best_name, best_score = listings, extractor.name, score
    return best, best_name


def extract_detail_page(
    html: str, page_url: str, learned: dict[str, Any] | None = None
) -> Listing | None:
    """Merge every strategy's read of a detail page, richest first."""
    results: list[tuple[float, Listing]] = []
    for extractor in all_extractors(learned):
        try:
            listing = extractor.detail_page(html, page_url)
        except Exception:
            continue
        if listing:
            score = sum(
                1 for v in (listing.title, listing.description, listing.price_text,
                            listing.location_text, listing.posted_text) if v
            ) + len(listing.attributes) * 0.1 + len(listing.image_urls) * 0.05
            results.append((score, listing))

    if not results:
        return None
    results.sort(key=lambda pair: pair[0], reverse=True)
    merged = results[0][1]
    for _, other in results[1:]:
        merged.merge(other)
    return merged


def find_next_page(html: str, page_url: str, page_param: str = "page") -> str | None:
    """Locate the next SERP page via rel=next, or a numeric pager link."""
    soup = _soup(html)
    link = soup.find("link", rel="next") or soup.find("a", rel="next")
    if link and link.get("href"):
        return _abs_url(link["href"], page_url)

    current = 1
    match = re.search(rf"[?&]{re.escape(page_param)}=(\d+)", page_url)
    if match:
        current = int(match.group(1))

    for anchor in soup.find_all("a", href=True):
        found = re.search(rf"[?&]{re.escape(page_param)}=(\d+)", anchor["href"])
        if found and int(found.group(1)) == current + 1:
            return _abs_url(anchor["href"], page_url)
    return None
