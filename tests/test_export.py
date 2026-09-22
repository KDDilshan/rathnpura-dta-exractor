import csv
import json

import pytest

from ikman.export import to_csv, to_jsonl
from ikman.models import Listing
from ikman.store import Store


@pytest.fixture
def populated(tmp_path):
    with Store(tmp_path / "t.sqlite") as store:
        store.upsert(Listing(
            url="https://ikman.lk/en/ad/axio-ratnapura-1", title="Toyota Axio",
            price_text="Rs 8,750,000", price_value=8750000.0, currency="LKR",
            town="Pelmadulla", district="Ratnapura", category="Cars",
            image_urls=["a.jpg", "b.jpg"],
            attributes={"Brand": "Toyota", "Mileage": "98,000 km"},
        ))
        store.upsert(Listing(
            url="https://ikman.lk/en/ad/land-balangoda-2", title="Tea land",
            price_value=4200000.0, town="Balangoda", district="Ratnapura",
            category="Land", attributes={"Land size": "3 acres"},
        ))
        yield store


def test_csv_flattens_attributes_into_columns(populated, tmp_path):
    out = tmp_path / "x.csv"
    assert to_csv(populated, out) == 2

    with out.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    assert {"attr_brand", "attr_mileage", "attr_land_size"} <= set(rows[0].keys())
    assert "attributes" not in rows[0]
    axio = next(r for r in rows if r["title"] == "Toyota Axio")
    assert axio["attr_brand"] == "Toyota"
    assert axio["attr_mileage"] == "98,000 km"
    assert axio["attr_land_size"] == ""          # not applicable to this row
    assert axio["image_urls"] == "a.jpg | b.jpg"
    assert axio["listing_id"]


def test_csv_can_keep_attributes_as_json(populated, tmp_path):
    out = tmp_path / "x.csv"
    to_csv(populated, out, flatten=False)
    with out.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert json.loads(rows[0]["attributes"])
    assert not any(k.startswith("attr_") for k in rows[0])


def test_csv_is_excel_friendly_utf8(populated, tmp_path):
    """The BOM makes Excel open Sinhala text correctly."""
    populated.upsert(Listing(url="https://ikman.lk/en/ad/sinhala-3",
                             title="රත්නපුර ඉඩම"))
    out = tmp_path / "x.csv"
    to_csv(populated, out)
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "රත්නපුර ඉඩම" in out.read_text(encoding="utf-8-sig")


def test_jsonl_one_object_per_line(populated, tmp_path):
    out = tmp_path / "x.jsonl"
    assert to_jsonl(populated, out) == 2
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    # Rows come back ordered by listing_id, so select rather than index.
    objs = {json.loads(line)["title"]: json.loads(line) for line in lines}
    axio = objs["Toyota Axio"]
    assert axio["attributes"]["Brand"] == "Toyota"
    assert axio["image_urls"] == ["a.jpg", "b.jpg"]
    assert axio["listing_id"]


def test_export_creates_missing_directories(populated, tmp_path):
    out = tmp_path / "deep" / "nested" / "x.csv"
    to_csv(populated, out)
    assert out.exists()


def test_empty_store_exports_header_only(tmp_path):
    with Store(tmp_path / "e.sqlite") as store:
        out = tmp_path / "e.csv"
        assert to_csv(store, out) == 0
        assert out.read_text(encoding="utf-8-sig").strip().startswith("listing_id")
