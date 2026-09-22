"""Tests for the Markdown-table importer and the location/price audit."""
import pytest

from ikman.gazetteer import district_of, find_town
from ikman.tabular import (
    audit_conflicts, import_text, normalise, parse_markdown_tables,
    parse_price_basis, parse_size, summarise, to_listing,
)

TABLE = """
| Title | Size | Location Listed | Price | Link |
|---|---|---|---|---|
| 15-Perch Land for Sale in Eheliyagoda | 15.0 perches | Ratnapura | Rs 4,300,000 total | View Ad |
| Land for Sale in Dambadeniya ,Giriulla U05 | 12.5 perches | Ratnapura | Rs 155,000 / perch | View Ad |
| LUXURY TEA ESTATE FOR SALE - PELMADULLA | 18.0 acres | Ratnapura | Rs 60,000,000 total | View Ad |
"""

REORDERED = """
| Title | Location | Size | Price |
|---|---|---|---|
| Land For Sale In Kahawatta | Ratnapura | 12.14 acres | Rs 31,500,000 total price |
"""


# ---- table parsing -------------------------------------------------------

def test_parses_rows_and_maps_aliased_headers():
    rows = parse_markdown_tables(TABLE)
    assert len(rows) == 3
    assert rows[0]["title"] == "15-Perch Land for Sale in Eheliyagoda"
    assert rows[0]["location"] == "Ratnapura"
    assert rows[0]["size"] == "15.0 perches"


def test_column_order_is_taken_from_each_header():
    """The second table puts Location before Size; rows must still bind right."""
    rows = parse_markdown_tables(TABLE + REORDERED)
    kahawatta = next(r for r in rows if "Kahawatta" in r["title"])
    assert kahawatta["size"] == "12.14 acres"
    assert kahawatta["location"] == "Ratnapura"


def test_unescaped_pipe_in_title_is_folded_back():
    text = """
| Title | Location | Size | Price |
|---|---|---|---|
| Eheliyagoda | 10P Highly Residential Land Plots | Ratnapura | 10.0 perches | Rs 250,000 per perch |
"""
    rows = parse_markdown_tables(text)
    assert len(rows) == 1
    assert rows[0]["title"] == "Eheliyagoda | 10P Highly Residential Land Plots"
    assert rows[0]["size"] == "10.0 perches"
    assert rows[0]["location"] == "Ratnapura"


def test_separator_and_prose_lines_are_ignored():
    text = "Here is the extracted data:\n" + TABLE + "\nSome trailing prose.\n"
    assert len(parse_markdown_tables(text)) == 3


def test_tables_are_numbered_so_rows_stay_traceable():
    rows = parse_markdown_tables(TABLE + REORDERED)
    assert {r["_table"] for r in rows} == {"1", "2"}


# ---- units ---------------------------------------------------------------

@pytest.mark.parametrize("text,perches,unit", [
    ("30.0 perches", 30.0, "perches"),
    ("18.0 acres", 2880.0, "acres"),
    ("2.5 acres", 400.0, "acres"),
    ("12.14 acres", 1942.4, "acres"),
    (None, None, None),
    ("unknown", None, None),
])
def test_parse_size(text, perches, unit):
    assert parse_size(text) == (perches, unit)


@pytest.mark.parametrize("text,amount,basis", [
    ("Rs 3,600,000 / perch", 3600000.0, "perch"),
    ("Rs 195,000 per perch", 195000.0, "perch"),
    ("Rs 9,000,000 / acre", 9000000.0, "acre"),
    ("Rs 135,000,000 total", 135000000.0, "total"),
    ("Rs 80,000,000 total price", 80000000.0, "total"),
    ("Rs 500,000", 500000.0, None),
    (None, None, None),
])
def test_parse_price_basis(text, amount, basis):
    assert parse_price_basis(text) == (amount, basis)


def test_per_perch_price_yields_a_total():
    row = normalise({"title": "Land in Eheliyagoda", "location": "Ratnapura",
                     "size": "10.0 perches", "price": "Rs 250,000 / perch"})
    assert row.price_per_perch == 250000.0
    assert row.price_total == 2500000.0


def test_total_price_yields_a_per_perch_rate():
    row = normalise({"title": "Land in Eheliyagoda", "location": "Ratnapura",
                     "size": "10.0 perches", "price": "Rs 2,000,000 total"})
    assert row.price_total == 2000000.0
    assert row.price_per_perch == 200000.0


def test_per_acre_price_is_converted_to_both_bases():
    row = normalise({"title": "Estate in Rakwana", "location": "Ratnapura",
                     "size": "4.0 acres", "price": "Rs 5,500,000 / acre"})
    assert row.size_perches == 640.0
    assert row.price_total == 22000000.0
    assert row.price_per_perch == pytest.approx(34375.0)


# ---- the location audit --------------------------------------------------

def test_title_town_overrides_the_listed_district():
    """This is the whole point: the location column is the seller's facet."""
    row = normalise({"title": "Land for Sale in Dambadeniya ,Giriulla U05",
                     "location": "Ratnapura", "size": "12.5 perches",
                     "price": "Rs 155,000 / perch"})
    assert row.town == "Dambadeniya"
    assert row.district == "Kurunegala"
    assert row.district_source == "title"
    assert any(f.startswith("location-mismatch") for f in row.flags)


def test_agreeing_location_is_not_flagged():
    row = normalise({"title": "15-Perch Land for Sale in Eheliyagoda",
                     "location": "Ratnapura", "size": "15.0 perches",
                     "price": "Rs 4,300,000 total"})
    assert (row.town, row.district) == ("Eheliyagoda", "Ratnapura")
    assert not any(f.startswith("location-mismatch") for f in row.flags)


def test_sinhala_place_name_resolves():
    row = normalise({"title": "වලස්මුල්ල නගරයෙන්මයි බිම් කොටස්",
                     "location": "Ratnapura", "size": "10.0 perches",
                     "price": "Rs 450,000 per perch"})
    assert row.district == "Hambantota"
    assert any(f.startswith("location-mismatch") for f in row.flags)


def test_unknown_town_is_reported_not_guessed():
    row = normalise({"title": "Tea Cultivated Land for Sale Nadurana",
                     "location": "Somewhere", "size": "5.0 acres",
                     "price": "Rs 30,000,000 total price"})
    assert row.district is None
    assert "district-unverified" in row.flags


@pytest.mark.parametrize("town,district", [
    ("Eheliyagoda", "Ratnapura"), ("Nittambuwa", "Gampaha"),
    ("Dambadeniya", "Kurunegala"), ("Kitulgala", "Kegalle"),
])
def test_gazetteer_lookups(town, district):
    assert find_town(f"Land for sale in {town}") == (town, district)


def test_district_of_handles_suffixes():
    assert district_of("Ratnapura District") == "Ratnapura"
    assert district_of("Ratnapura New Town") == "Ratnapura"
    assert district_of("Nowhere") is None


# ---- the price audit -----------------------------------------------------

def test_duplicate_with_a_tenfold_price_is_flagged():
    rows = [
        normalise({"title": "Plots in Eheliyagoda", "location": "Ratnapura",
                   "size": "10.0 perches", "price": "Rs 200,000 per perch"}),
        normalise({"title": "Plots in Eheliyagoda", "location": "Ratnapura",
                   "size": "10.0 perches", "price": "Rs 2,000,000 total"}),
        normalise({"title": "Plots in Eheliyagoda", "location": "Ratnapura",
                   "size": "10.0 perches", "price": "Rs 2,000,000 per perch"}),
    ]
    conflicts = audit_conflicts(rows)
    assert len(conflicts) == 1
    outlier = next(r for r in rows if r.price_total == 20000000.0)
    assert "price-conflicts-with-duplicate" in outlier.flags


def test_consistent_duplicates_are_not_flagged():
    rows = [
        normalise({"title": "Plots in Eheliyagoda", "location": "Ratnapura",
                   "size": "10.0 perches", "price": "Rs 200,000 per perch"}),
        normalise({"title": "Plots in Eheliyagoda", "location": "Ratnapura",
                   "size": "10.0 perches", "price": "Rs 2,000,000 total"}),
    ]
    assert audit_conflicts(rows) == []


def test_title_acreage_conflicting_with_size_is_flagged():
    row = normalise({"title": "(AF860) 28 Acres Commercial Estate in Eheliyagoda",
                     "location": "Ratnapura", "size": "21.0 perches",
                     "price": "Rs 80,000,000 total"})
    assert "size-unit-conflicts-with-title" in row.flags


def test_implausible_total_is_flagged():
    row = normalise({"title": "28 Acres Estate in Eheliyagoda", "location": "Ratnapura",
                     "size": "28.0 acres", "price": "Rs 80,000,000 per acre"})
    assert "total-implausibly-high" in row.flags


# ---- loading -------------------------------------------------------------

def test_duplicate_rows_collapse_to_one_advert():
    doubled = TABLE + TABLE.split("|---|---|---|---|---|")[1]
    rows, _ = import_text(doubled)
    keys = {r.row_key for r in rows}
    assert len(rows) > len(keys)


def test_to_listing_carries_normalised_values_and_flags():
    row = normalise({"title": "Land for Sale in Dambadeniya ,Giriulla U05",
                     "location": "Ratnapura", "size": "12.5 perches",
                     "price": "Rs 155,000 / perch"})
    listing = to_listing(row)
    assert listing.url.startswith("imported:land/")
    assert listing.district == "Kurunegala"
    assert listing.category == "Land"
    assert listing.price_value == 1937500.0
    assert listing.attributes["Price per perch"] == 155000
    assert listing.attributes["Size (perches)"] == 12.5
    assert listing.attributes["Location as listed"] == "Ratnapura"
    assert "location-mismatch" in listing.attributes["Data flags"]


def test_summarise_counts_districts_and_flags():
    rows, _ = import_text(TABLE)
    summary = summarise(rows)
    assert summary["rows_parsed"] == 3
    assert summary["by_district"]["Ratnapura"] == 2
    assert summary["by_district"]["Kurunegala"] == 1
    assert summary["in_ratnapura"] == 2


def test_empty_input_is_handled():
    rows, conflicts = import_text("no tables here at all")
    assert rows == []
    assert conflicts == []
