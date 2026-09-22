"""SQLite persistence. Upserts listings and tracks crawl progress so an
interrupted run resumes instead of starting over."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator
import json
import sqlite3

from .models import Listing, ROW_COLUMNS

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    listing_id      TEXT PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT,
    price_text      TEXT,
    price_value     REAL,
    currency        TEXT,
    price_qualifier TEXT,
    category        TEXT,
    subcategory     TEXT,
    location_text   TEXT,
    town            TEXT,
    district        TEXT,
    description     TEXT,
    condition       TEXT,
    seller_name     TEXT,
    seller_type     TEXT,
    is_promoted     INTEGER DEFAULT 0,
    posted_text     TEXT,
    posted_at       TEXT,
    image_urls      TEXT,
    attributes      TEXT,
    source_page     TEXT,
    extracted_by    TEXT,
    scraped_at      TEXT,
    detail_fetched  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_listings_town     ON listings(town);
CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);
CREATE INDEX IF NOT EXISTS idx_listings_detail   ON listings(detail_fetched);
CREATE INDEX IF NOT EXISTS idx_listings_price    ON listings(price_value);

CREATE TABLE IF NOT EXISTS pages (
    url          TEXT PRIMARY KEY,
    kind         TEXT,          -- serp | detail
    status       INTEGER,
    listings     INTEGER DEFAULT 0,
    strategy     TEXT,
    next_url     TEXT,
    error        TEXT,
    visited_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at   TEXT,
    config     TEXT,
    notes      TEXT
);
"""


class Store:
    def __init__(self, path: str | Path = "data/ikman.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(pages)")}
        if "next_url" not in columns:
            self.conn.execute("ALTER TABLE pages ADD COLUMN next_url TEXT")

    # ---- listings ----------------------------------------------------------

    def upsert(self, listing: Listing, detail_fetched: bool = False) -> bool:
        """Insert, or merge into an existing row. True when the row is new.

        Merge rather than replace: a SERP card and a detail page each know
        things the other does not, and a re-crawl should not blank a field.
        """
        existing = self.get(listing.url)
        if existing:
            merged = existing.merge(listing)
            row = merged.to_row()
            row["detail_fetched"] = int(
                detail_fetched or self.is_detail_fetched(listing.url)
            )
            assignments = ", ".join(f"{c}=:{c}" for c in ROW_COLUMNS if c != "listing_id")
            self.conn.execute(
                f"UPDATE listings SET {assignments}, detail_fetched=:detail_fetched "
                "WHERE listing_id=:listing_id",
                row,
            )
            self.conn.commit()
            return False

        row = listing.to_row()
        row["detail_fetched"] = int(detail_fetched)
        cols = ROW_COLUMNS + ["detail_fetched"]
        self.conn.execute(
            f"INSERT INTO listings ({', '.join(cols)}) "
            f"VALUES ({', '.join(':' + c for c in cols)})",
            row,
        )
        self.conn.commit()
        return True

    def upsert_many(self, listings: list[Listing]) -> tuple[int, int]:
        """-> (new, updated)."""
        new = sum(1 for listing in listings if self.upsert(listing))
        return new, len(listings) - new

    @staticmethod
    def _to_listing(row: sqlite3.Row) -> Listing:
        data = {k: row[k] for k in row.keys() if k in ROW_COLUMNS}
        data.pop("listing_id", None)
        data["image_urls"] = json.loads(data.get("image_urls") or "[]")
        data["attributes"] = json.loads(data.get("attributes") or "{}")
        data["is_promoted"] = bool(data.get("is_promoted"))
        return Listing(**data)

    def get(self, url: str) -> Listing | None:
        row = self.conn.execute("SELECT * FROM listings WHERE url=?", (url,)).fetchone()
        return self._to_listing(row) if row else None

    def is_detail_fetched(self, url: str) -> bool:
        row = self.conn.execute(
            "SELECT detail_fetched FROM listings WHERE url=?", (url,)
        ).fetchone()
        return bool(row and row["detail_fetched"])

    def mark_detail_fetched(self, url: str) -> None:
        self.conn.execute("UPDATE listings SET detail_fetched=1 WHERE url=?", (url,))
        self.conn.commit()

    def pending_details(self, limit: int | None = None) -> list[str]:
        sql = "SELECT url FROM listings WHERE detail_fetched=0 ORDER BY scraped_at"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r["url"] for r in self.conn.execute(sql)]

    def iter_listings(self, district: str | None = None) -> Iterator[Listing]:
        sql = "SELECT * FROM listings"
        params: tuple[Any, ...] = ()
        if district:
            sql += " WHERE district = ?"
            params = (district,)
        sql += " ORDER BY listing_id"
        for row in self.conn.execute(sql, params):
            yield self._to_listing(row)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM listings").fetchone()["n"]

    # ---- crawl progress ----------------------------------------------------

    def record_page(self, url: str, kind: str, status: int, listings: int = 0,
                    strategy: str | None = None, error: str | None = None,
                    next_url: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO pages (url, kind, status, listings, strategy, next_url, error) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET "
            "status=excluded.status, listings=excluded.listings, "
            "strategy=excluded.strategy, next_url=excluded.next_url, "
            "error=excluded.error, visited_at=CURRENT_TIMESTAMP",
            (url, kind, status, listings, strategy, next_url, error),
        )
        self.conn.commit()

    def visited(self, url: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM pages WHERE url=? AND error IS NULL AND status < 400", (url,)
        ).fetchone()
        return row is not None

    def next_page_of(self, url: str) -> str | None:
        """The next-page link recorded when this page was last crawled.

        Resuming relies on this: a visited page with no recorded successor means
        the query genuinely ended there, so the crawler must stop rather than
        probe further page numbers that do not exist.
        """
        row = self.conn.execute(
            "SELECT next_url FROM pages WHERE url=?", (url,)
        ).fetchone()
        return row["next_url"] if row else None

    def start_run(self, config: dict[str, Any], notes: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (config, notes) VALUES (?,?)",
            (json.dumps(config, default=str), notes),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def end_run(self, run_id: int, notes: str = "") -> None:
        self.conn.execute(
            "UPDATE runs SET ended_at=CURRENT_TIMESTAMP, "
            "notes=COALESCE(NULLIF(notes,''),'') || ? WHERE id=?",
            (notes, run_id),
        )
        self.conn.commit()

    # ---- reporting ---------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        cur = self.conn.execute
        return {
            "listings": self.count(),
            "with_detail": cur("SELECT COUNT(*) n FROM listings WHERE detail_fetched=1"
                               ).fetchone()["n"],
            "with_price": cur("SELECT COUNT(*) n FROM listings WHERE price_value IS NOT NULL"
                              ).fetchone()["n"],
            "pages_visited": cur("SELECT COUNT(*) n FROM pages").fetchone()["n"],
            "by_town": {r["town"] or "(unknown)": r["n"] for r in cur(
                "SELECT town, COUNT(*) n FROM listings GROUP BY town ORDER BY n DESC")},
            "by_category": {r["category"] or "(unknown)": r["n"] for r in cur(
                "SELECT category, COUNT(*) n FROM listings GROUP BY category "
                "ORDER BY n DESC LIMIT 25")},
            "by_strategy": {r["extracted_by"] or "(unknown)": r["n"] for r in cur(
                "SELECT extracted_by, COUNT(*) n FROM listings GROUP BY extracted_by")},
        }

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
