"""Export the collected listings to CSV, JSONL or Excel."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import csv
import json

from .models import Listing, ROW_COLUMNS
from .store import Store

# Flattened attribute keys are appended after the fixed columns so
# category-specific facets (Mileage, Bedrooms, ...) each get their own column.
FLAT_PREFIX = "attr_"


def _rows(listings: Iterable[Listing], flatten: bool) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    attr_keys: list[str] = []
    seen_attrs: set[str] = set()

    for listing in listings:
        row = listing.to_row()
        row["image_urls"] = " | ".join(listing.image_urls)
        if flatten:
            row.pop("attributes", None)
            for key, value in listing.attributes.items():
                column = FLAT_PREFIX + key.strip().replace(" ", "_").lower()
                if column not in seen_attrs:
                    seen_attrs.add(column)
                    attr_keys.append(column)
                row[column] = value
        rows.append(row)

    base = [c for c in ROW_COLUMNS if not (flatten and c == "attributes")]
    return rows, base + sorted(attr_keys)


def to_csv(store: Store, path: str | Path, flatten: bool = True) -> int:
    rows, columns = _rows(store.iter_listings(), flatten)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def to_jsonl(store: Store, path: str | Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for listing in store.iter_listings():
            handle.write(json.dumps(listing.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count


def to_excel(store: Store, path: str | Path, flatten: bool = True) -> int:
    try:
        from openpyxl import Workbook
    except ImportError as exc:                       # pragma: no cover
        raise RuntimeError(
            "Excel export needs openpyxl: pip install openpyxl"
        ) from exc

    rows, columns = _rows(store.iter_listings(), flatten)
    book = Workbook()
    sheet = book.active
    sheet.title = "Ratnapura listings"
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(c) for c in columns])
    sheet.freeze_panes = "A2"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    book.save(path)
    return len(rows)


def export_all(store: Store, out_dir: str | Path = "out",
               stem: str = "ratnapura-ikman") -> dict[str, str]:
    out_dir = Path(out_dir)
    written = {
        "csv": str(out_dir / f"{stem}.csv"),
        "jsonl": str(out_dir / f"{stem}.jsonl"),
    }
    to_csv(store, written["csv"])
    to_jsonl(store, written["jsonl"])
    return written
