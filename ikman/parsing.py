"""Value normalisation: prices, relative dates, locations, whitespace."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from .config import RATNAPURA_TOWNS, DISTRICT_NAME

_WS = re.compile(r"\s+")

_PRICE_QUALIFIERS = [
    "negotiable", "per month", "per day", "per week", "per year", "per perch",
    "per acre", "per hour", "onwards", "starting from", "fixed",
]

# "Rs 2,500,000", "Rs. 45000", "LKR 1,200", "2,500,000"
_PRICE_RE = re.compile(
    r"(?P<cur>Rs\.?|LKR|රු\.?)?\s*(?P<num>\d[\d,\s]*(?:\.\d+)?)",
    re.IGNORECASE,
)

_TOWN_LOOKUP = {t.lower(): t for t in RATNAPURA_TOWNS}


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    out = _WS.sub(" ", text.replace("\xa0", " ")).strip()
    return out or None


def parse_price(text: str | None) -> tuple[float | None, str | None, str | None]:
    """-> (value, currency, qualifier). Returns (None, None, None) when absent.

    Non-numeric prices such as "Ask for price" or "Free" yield no value but are
    still reported through the qualifier so the distinction survives export.
    """
    if not text:
        return None, None, None
    low = text.lower()

    qualifier = next((q.title() for q in _PRICE_QUALIFIERS if q in low), None)

    if "free" in low and not any(ch.isdigit() for ch in text):
        return 0.0, "LKR", qualifier or "Free"
    if any(p in low for p in ("ask for price", "negotiable price", "on request")):
        return None, None, qualifier or "Ask for price"

    match = _PRICE_RE.search(text)
    if not match:
        return None, None, qualifier

    raw = match.group("num").replace(",", "").replace(" ", "")
    try:
        value = float(raw)
    except ValueError:
        return None, None, qualifier

    cur = match.group("cur")
    currency = "LKR" if cur or "rs" in low or "lkr" in low else None
    return value, currency, qualifier


def parse_posted(text: str | None, now: datetime | None = None) -> str | None:
    """Normalise ikman's relative timestamps to an ISO-8601 UTC string."""
    if not text:
        return None
    now = now or datetime.now(timezone.utc)
    low = clean(text).lower()

    if "just now" in low or "moments ago" in low:
        return now.isoformat(timespec="seconds")
    if "today" in low:
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(
            timespec="seconds"
        )
    if "yesterday" in low:
        day = now - timedelta(days=1)
        return day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(
            timespec="seconds"
        )

    rel = re.search(
        r"(\d+)\s*(second|minute|min|hour|hr|day|week|month|year)s?\s*ago", low
    )
    if rel:
        n = int(rel.group(1))
        unit = rel.group(2)
        deltas = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "min": timedelta(minutes=n),
            "hour": timedelta(hours=n),
            "hr": timedelta(hours=n),
            "day": timedelta(days=n),
            "week": timedelta(weeks=n),
            "month": timedelta(days=30 * n),
            "year": timedelta(days=365 * n),
        }
        return (now - deltas[unit]).isoformat(timespec="seconds")

    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"):
        try:
            naive = datetime.strptime(clean(text), fmt)
            return naive.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def split_location(text: str | None) -> tuple[str | None, str | None]:
    """-> (town, district) from strings like "Pelmadulla, Ratnapura".

    ikman orders location facets most-specific-first, so position decides which
    part is the town; the town table only canonicalises spelling and case. This
    matters because "Ratnapura" names both a town and the district, and a pure
    table lookup would let the district overwrite a more specific town.
    """
    if not text:
        return None, None
    parts = [p for p in (clean(p) for p in clean(text).split(",")) if p]
    if not parts:
        return None, None

    def is_district(part: str) -> bool:
        key = part.lower().replace(" district", "").strip()
        return key == DISTRICT_NAME.lower()

    district = DISTRICT_NAME if any(is_district(p) for p in parts) else None

    town = parts[0]
    # Only fall past the first part when it is purely the district label and a
    # more specific part follows (e.g. "Ratnapura District, Pelmadulla").
    if len(parts) > 1 and is_district(town):
        town = parts[1]

    canonical = _TOWN_LOOKUP.get(town.lower().replace(" district", "").strip())
    return (canonical or town), district
