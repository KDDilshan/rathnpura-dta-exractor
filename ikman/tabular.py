"""Import listings from Markdown tables (e.g. pasted from a browser extraction).

Handles what the tables actually contain rather than an idealised form: column
orders and header names differ between pastes, titles contain unescaped pipes,
land sizes mix perches and acres, and prices are quoted per-perch, per-acre or
as a total. Everything is normalised to a common basis and then audited, because
two fields in this data are demonstrably unreliable:

* the **location** column is the seller's chosen facet, not the advert's town;
* the **price basis** ("/ perch" vs "total") disagrees between pastes for
  adverts that are otherwise identical.

Nothing is silently corrected. Each row carries the original text plus the
normalised values and a flag saying what looks wrong, so you can decide.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
import hashlib
import re

from .gazetteer import RATNAPURA, district_of, find_town
from .models import Listing
from .parsing import clean

PERCHES_PER_ACRE = 160.0
SQM_PER_PERCH = 25.2929

# Plausibility envelope for Sri Lankan land, wide on purpose: it is here to
# catch unit errors (a 100x mistake), not to second-guess the market.
MIN_SENSIBLE_PER_PERCH = 10_000.0
MAX_SENSIBLE_PER_PERCH = 5_000_000.0
MAX_SENSIBLE_TOTAL = 500_000_000.0

# Outside the western urban districts a per-perch rate this high almost always
# means a total price was read as a rate.
HIGH_PER_PERCH_OUTSIDE_CITY = 1_500_000.0
CITY_DISTRICTS = {"Colombo", "Gampaha", "Kalutara"}

# How far an advert's implied total may sit from its duplicates' median.
OUTLIER_RATIO = 3.0

_HEADER_ALIASES = {
    "title": "title", "name": "title", "advert": "title",
    "size": "size", "land size": "size", "extent": "size", "area": "size",
    "location": "location", "location listed": "location", "district": "location",
    "price": "price", "asking price": "price",
    "link": "link", "url": "link", "ad": "link",
}

_SEPARATOR_RE = re.compile(r"^\|?[\s:|-]+\|?$")


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _map_headers(cells: list[str]) -> list[str] | None:
    mapped = [_HEADER_ALIASES.get(c.strip().lower()) for c in cells]
    if mapped.count("title") == 1 and "price" in mapped:
        return mapped
    return None


def parse_markdown_tables(text: str) -> list[dict[str, str]]:
    """Extract rows from one or more Markdown tables in `text`.

    Several tables with different column orders may be concatenated; each header
    row re-binds the columns for the rows that follow. Titles containing an
    unescaped ``|`` produce extra cells, which are folded back into the title.
    """
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    table_index = 0

    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        if _SEPARATOR_RE.match(line.strip()):
            continue

        cells = _split_row(line)
        as_header = _map_headers(cells)
        if as_header:
            headers = as_header
            table_index += 1
            continue
        if not headers:
            continue

        # An unescaped pipe inside the title yields surplus cells; the title is
        # the first column, so fold the surplus back into it.
        if len(cells) > len(headers):
            surplus = len(cells) - len(headers)
            cells = [" | ".join(cells[: surplus + 1])] + cells[surplus + 1:]
        elif len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))

        row = {"_table": str(table_index)}
        for key, value in zip(headers, cells):
            if key:
                row[key] = value
        if row.get("title"):
            rows.append(row)
    return rows


def parse_size(text: str | None) -> tuple[float | None, str | None]:
    """-> (perches, original unit). Acres are converted; unknown units are kept."""
    if not text:
        return None, None
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        return None, None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None, None

    low = text.lower()
    if "acre" in low:
        return value * PERCHES_PER_ACRE, "acres"
    if "perch" in low or low.strip().endswith("p"):
        return value, "perches"
    if "sq" in low and ("m" in low or "meter" in low or "metre" in low):
        return value / SQM_PER_PERCH, "sqm"
    return value, None


def parse_price_basis(text: str | None) -> tuple[float | None, str | None]:
    """-> (amount, basis) where basis is 'perch' | 'acre' | 'total' | None."""
    if not text:
        return None, None
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        return None, None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None, None

    low = text.lower()
    if "perch" in low:
        basis = "perch"
    elif "acre" in low:
        basis = "acre"
    elif "total" in low:
        basis = "total"
    else:
        basis = None
    return amount, basis


@dataclass
class ImportedRow:
    title: str
    location_listed: str | None
    size_text: str | None
    price_text: str | None
    size_perches: float | None = None
    size_unit: str | None = None
    price_amount: float | None = None
    price_basis: str | None = None
    price_total: float | None = None
    price_per_perch: float | None = None
    town: str | None = None
    district: str | None = None
    district_source: str | None = None
    flags: list[str] = field(default_factory=list)
    source_table: str | None = None

    @property
    def row_key(self) -> str:
        """Identity for deduplication: the advert, not the paste it came from."""
        basis = f"{self.title.strip().lower()}|{self.size_perches}|{self.price_amount}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def normalise(row: dict[str, str]) -> ImportedRow:
    title = clean(row.get("title")) or ""
    out = ImportedRow(
        title=title,
        location_listed=clean(row.get("location")),
        size_text=clean(row.get("size")),
        price_text=clean(row.get("price")),
        source_table=row.get("_table"),
    )

    out.size_perches, out.size_unit = parse_size(out.size_text)
    out.price_amount, out.price_basis = parse_price_basis(out.price_text)

    # Resolve the town from the title first: it is written by the seller about
    # the actual property, whereas the location column is a site facet.
    town, district = find_town(title)
    if town:
        out.town, out.district, out.district_source = town, district, "title"
    else:
        listed_town, listed_district = find_town(out.location_listed)
        if listed_town:
            out.town, out.district = listed_town, listed_district
            out.district_source = "location-column"
        else:
            out.district = district_of(out.location_listed)
            out.district_source = "location-column" if out.district else None

    # Money: derive total and per-perch from whichever basis was quoted.
    amount, perches = out.price_amount, out.size_perches
    if amount is not None:
        if out.price_basis == "perch":
            out.price_per_perch = amount
            out.price_total = amount * perches if perches else None
        elif out.price_basis == "acre":
            out.price_total = amount * (perches / PERCHES_PER_ACRE) if perches else None
            out.price_per_perch = amount / PERCHES_PER_ACRE
        else:
            out.price_total = amount
            out.price_per_perch = amount / perches if perches else None

    if out.price_basis is None and amount is not None:
        out.flags.append("price-basis-unstated")
    if out.size_perches is None:
        out.flags.append("size-unparsed")
    if out.price_per_perch is not None:
        if out.price_per_perch < MIN_SENSIBLE_PER_PERCH:
            out.flags.append("per-perch-implausibly-low")
        elif out.price_per_perch > MAX_SENSIBLE_PER_PERCH:
            out.flags.append("per-perch-implausibly-high")
    if out.price_total is not None and out.price_total > MAX_SENSIBLE_TOTAL:
        out.flags.append("total-implausibly-high")
    if (out.price_per_perch is not None
            and out.price_per_perch >= HIGH_PER_PERCH_OUTSIDE_CITY
            and out.district not in CITY_DISTRICTS):
        out.flags.append("per-perch-high-for-district")

    listed_district = district_of(out.location_listed) or (
        find_town(out.location_listed)[1]
    )
    if out.district and listed_district and out.district != listed_district:
        out.flags.append(f"location-mismatch:listed-{listed_district}-"
                         f"actually-{out.district}")
    elif out.district is None:
        out.flags.append("district-unverified")

    # A title claiming acres against a size given in perches (or vice versa).
    title_acres = re.search(r"(\d+(?:\.\d+)?)\s*acres?", title, re.IGNORECASE)
    if title_acres and out.size_unit == "perches":
        out.flags.append("size-unit-conflicts-with-title")

    return out


def audit_conflicts(rows: list[ImportedRow]) -> list[dict[str, Any]]:
    """Flag adverts whose implied total price disagrees with their near-identical twins.

    Comparing the quoted amount alone misses the real defect: the same advert,
    same size, appears as "Rs 200,000 / perch" in one paste and
    "Rs 2,000,000 / perch" in another - ten times apart, because one of them
    took a total for a per-perch rate. Grouping by title+size and comparing the
    *implied total* against the group median is what surfaces those.
    """
    groups: dict[tuple[str, float | None], list[ImportedRow]] = {}
    for row in rows:
        groups.setdefault((row.title.strip().lower(), row.size_perches), []).append(row)

    conflicts: list[dict[str, Any]] = []
    for (title, size), group in groups.items():
        totals = [r.price_total for r in group if r.price_total]
        if len(totals) < 2:
            continue
        ordered = sorted(totals)
        median = ordered[len(ordered) // 2]
        if not median:
            continue
        outliers = [r for r in group
                    if r.price_total and (r.price_total / median > OUTLIER_RATIO
                                          or median / r.price_total > OUTLIER_RATIO)]
        if not outliers:
            continue
        for row in outliers:
            if "price-conflicts-with-duplicate" not in row.flags:
                row.flags.append("price-conflicts-with-duplicate")
        conflicts.append({
            "title": title,
            "size_perches": size,
            "median_total": median,
            "variants": sorted({
                f"{r.price_text} => total {r.price_total:,.0f}" for r in group
                if r.price_total
            }),
        })
    return conflicts


def to_listing(row: ImportedRow) -> Listing:
    """Map an imported row onto the project's Listing record.

    These rows carry no advert URL, so a synthetic ``imported:`` identifier is
    used. It is derived from title+size+price, which makes re-importing the same
    paste idempotent and collapses exact duplicates across pages.
    """
    attributes: dict[str, Any] = {
        "Land size": row.size_text,
        "Size (perches)": round(row.size_perches, 2) if row.size_perches else None,
        "Size unit as given": row.size_unit,
        "Price basis": row.price_basis,
        "Price amount": row.price_amount,
        "Price per perch": round(row.price_per_perch) if row.price_per_perch else None,
        "Total price": round(row.price_total) if row.price_total else None,
        "Location as listed": row.location_listed,
        "District source": row.district_source,
        "Data flags": ", ".join(row.flags) or None,
        "Source table": row.source_table,
    }
    return Listing(
        url=f"imported:land/{row.row_key}",
        title=row.title,
        price_text=row.price_text,
        price_value=row.price_total,
        currency="LKR" if row.price_amount else None,
        price_qualifier=(f"per {row.price_basis}" if row.price_basis in
                         ("perch", "acre") else row.price_basis),
        category="Land",
        subcategory="Land for sale",
        location_text=row.location_listed,
        town=row.town,
        district=row.district,
        attributes={k: v for k, v in attributes.items() if v is not None},
        source_page="markdown-import",
        extracted_by="table-import",
    )


def import_text(text: str) -> tuple[list[ImportedRow], list[dict[str, Any]]]:
    rows = [normalise(r) for r in parse_markdown_tables(text)]
    conflicts = audit_conflicts(rows)
    return rows, conflicts


def import_file(path: str | Path) -> tuple[list[ImportedRow], list[dict[str, Any]]]:
    return import_text(Path(path).read_text(encoding="utf-8"))


def summarise(rows: Iterable[ImportedRow]) -> dict[str, Any]:
    rows = list(rows)
    by_district: dict[str, int] = {}
    by_flag: dict[str, int] = {}
    for row in rows:
        by_district[row.district or "(unverified)"] = \
            by_district.get(row.district or "(unverified)", 0) + 1
        for flag in row.flags:
            key = flag.split(":")[0]
            by_flag[key] = by_flag.get(key, 0) + 1

    unique = {row.row_key for row in rows}
    in_district = [r for r in rows if r.district == RATNAPURA]
    return {
        "rows_parsed": len(rows),
        "unique_adverts": len(unique),
        "duplicate_rows": len(rows) - len(unique),
        "by_district": dict(sorted(by_district.items(), key=lambda kv: -kv[1])),
        "in_ratnapura": len(in_district),
        "flags": dict(sorted(by_flag.items(), key=lambda kv: -kv[1])),
    }
