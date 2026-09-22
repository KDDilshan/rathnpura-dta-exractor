from datetime import datetime, timezone

import pytest

from ikman.parsing import clean, parse_posted, parse_price, split_location

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,value,currency,qualifier", [
    ("Rs 2,500,000", 2500000.0, "LKR", None),
    ("Rs. 45000 Negotiable", 45000.0, "LKR", "Negotiable"),
    ("LKR 1,200 per month", 1200.0, "LKR", "Per Month"),
    ("Rs 25,000 per day", 25000.0, "LKR", "Per Day"),
    ("Free", 0.0, "LKR", "Free"),
    ("Ask for price", None, None, "Ask for price"),
    ("1500", 1500.0, None, None),
    (None, None, None, None),
    ("", None, None, None),
    ("no digits here", None, None, None),
])
def test_parse_price(text, value, currency, qualifier):
    assert parse_price(text) == (value, currency, qualifier)


def test_parse_price_handles_decimal_and_spaces():
    assert parse_price("Rs 1 250.50")[0] == 1250.50


@pytest.mark.parametrize("text,expected", [
    ("2 days ago", "2026-09-20T12:00:00+00:00"),
    ("3 hours ago", "2026-09-22T09:00:00+00:00"),
    ("30 minutes ago", "2026-09-22T11:30:00+00:00"),
    ("Today", "2026-09-22T00:00:00+00:00"),
    ("Yesterday", "2026-09-21T00:00:00+00:00"),
    ("just now", "2026-09-22T12:00:00+00:00"),
    ("12 Jan 2025", "2025-01-12T00:00:00+00:00"),
    ("2025-03-04", "2025-03-04T00:00:00+00:00"),
])
def test_parse_posted(text, expected):
    assert parse_posted(text, NOW) == expected


def test_parse_posted_unknown_returns_none():
    assert parse_posted("sometime last season", NOW) is None
    assert parse_posted(None) is None


@pytest.mark.parametrize("text,town,district", [
    ("Pelmadulla, Ratnapura", "Pelmadulla", "Ratnapura"),
    ("Embilipitiya, Ratnapura District", "Embilipitiya", "Ratnapura"),
    ("Ratnapura", "Ratnapura", "Ratnapura"),
    ("Colombo, Colombo", "Colombo", None),
    ("  eheliyagoda , ratnapura ", "Eheliyagoda", "Ratnapura"),
    ("", None, None),
    (None, None, None),
])
def test_split_location(text, town, district):
    assert split_location(text) == (town, district)


def test_split_location_does_not_let_district_shadow_town():
    """"Ratnapura" names a town and the district; the town must stay specific."""
    assert split_location("Kalawana, Ratnapura")[0] == "Kalawana"
    assert split_location("Ratnapura District, Pelmadulla") == ("Pelmadulla", "Ratnapura")


def test_clean_collapses_whitespace_and_nbsp():
    assert clean("  a\xa0 b\n\tc  ") == "a b c"
    assert clean("   ") is None
    assert clean(None) is None
