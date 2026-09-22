import pytest

from ikman.models import Listing
from ikman.store import Store

URL = "https://ikman.lk/en/ad/toyota-axio-2015-ratnapura-4f2a11"


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "t.sqlite") as s:
        yield s


def test_insert_then_merge(store):
    assert store.upsert(Listing(url=URL, title="Axio", price_value=100.0)) is True
    assert store.upsert(Listing(url=URL, description="Nice",
                                attributes={"Brand": "Toyota"})) is False
    got = store.get(URL)
    assert (got.title, got.price_value) == ("Axio", 100.0)
    assert got.description == "Nice"
    assert got.attributes == {"Brand": "Toyota"}
    assert store.count() == 1


def test_merge_never_blanks_a_known_field(store):
    store.upsert(Listing(url=URL, title="Axio", town="Pelmadulla",
                         image_urls=["a.jpg"]))
    store.upsert(Listing(url=URL))          # an empty re-scrape
    got = store.get(URL)
    assert (got.title, got.town, got.image_urls) == ("Axio", "Pelmadulla", ["a.jpg"])


def test_merge_unions_images_without_duplicates(store):
    store.upsert(Listing(url=URL, image_urls=["a.jpg", "b.jpg"]))
    store.upsert(Listing(url=URL, image_urls=["b.jpg", "c.jpg"]))
    assert store.get(URL).image_urls == ["a.jpg", "b.jpg", "c.jpg"]


def test_attributes_merge_rather_than_replace(store):
    store.upsert(Listing(url=URL, attributes={"Brand": "Toyota"}))
    store.upsert(Listing(url=URL, attributes={"Mileage": "98,000 km"}))
    assert store.get(URL).attributes == {"Brand": "Toyota", "Mileage": "98,000 km"}


def test_detail_flag_survives_a_later_upsert(store):
    store.upsert(Listing(url=URL, title="Axio"))
    assert store.pending_details() == [URL]
    store.mark_detail_fetched(URL)
    assert store.pending_details() == []
    store.upsert(Listing(url=URL, title="Axio updated"))
    assert store.is_detail_fetched(URL) is True
    assert store.pending_details() == []


def test_listing_id_is_stable_across_query_strings(store):
    a = Listing(url=URL)
    b = Listing(url=URL + "?utm_source=x")
    assert a.listing_id == b.listing_id


def test_visited_ignores_errors_and_http_failures(store):
    store.record_page("https://ikman.lk/a", "serp", 200, 3, "selectors")
    store.record_page("https://ikman.lk/b", "serp", 0, error="boom")
    store.record_page("https://ikman.lk/c", "serp", 503)
    assert store.visited("https://ikman.lk/a") is True
    assert store.visited("https://ikman.lk/b") is False
    assert store.visited("https://ikman.lk/c") is False
    assert store.visited("https://ikman.lk/unknown") is False


def test_next_page_of_round_trips(store):
    store.record_page("https://ikman.lk/p1", "serp", 200, 3, "selectors",
                      next_url="https://ikman.lk/p2")
    store.record_page("https://ikman.lk/p2", "serp", 200, 3, "selectors")
    assert store.next_page_of("https://ikman.lk/p1") == "https://ikman.lk/p2"
    assert store.next_page_of("https://ikman.lk/p2") is None
    assert store.next_page_of("https://ikman.lk/never") is None


def test_roundtrip_preserves_types(store):
    store.upsert(Listing(url=URL, is_promoted=True, price_value=1.5,
                         image_urls=["a.jpg"], attributes={"n": 1}))
    got = store.get(URL)
    assert got.is_promoted is True
    assert got.price_value == 1.5
    assert got.image_urls == ["a.jpg"]
    assert got.attributes == {"n": 1}


def test_unicode_survives_the_roundtrip(store):
    store.upsert(Listing(url=URL, title="රත්නපුර ඉඩම", description="හොඳ තත්වයේ"))
    got = store.get(URL)
    assert got.title == "රත්නපුර ඉඩම"
    assert got.description == "හොඳ තත්වයේ"


def test_stats_groups_by_town_and_category(store):
    store.upsert(Listing(url=URL + "1", town="Ratnapura", category="Cars",
                         price_value=10.0))
    store.upsert(Listing(url=URL + "2", town="Ratnapura", category="Cars"))
    store.upsert(Listing(url=URL + "3", town="Balangoda", category="Land"))
    stats = store.stats()
    assert stats["listings"] == 3
    assert stats["by_town"]["Ratnapura"] == 2
    assert stats["by_category"]["Land"] == 1
    assert stats["with_price"] == 1


def test_reopening_the_database_keeps_data(tmp_path):
    path = tmp_path / "t.sqlite"
    with Store(path) as s:
        s.upsert(Listing(url=URL, title="Axio"))
    with Store(path) as s:
        assert s.count() == 1
        assert s.get(URL).title == "Axio"


def test_migration_adds_next_url_to_an_older_database(tmp_path):
    """A database written before next_url existed must open and gain the column."""
    import sqlite3
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE pages (url TEXT PRIMARY KEY, kind TEXT, status INTEGER,"
        " listings INTEGER DEFAULT 0, strategy TEXT, error TEXT,"
        " visited_at TEXT DEFAULT CURRENT_TIMESTAMP);"
    )
    conn.commit()
    conn.close()

    with Store(path) as s:
        s.record_page("https://ikman.lk/p1", "serp", 200, next_url="https://ikman.lk/p2")
        assert s.next_page_of("https://ikman.lk/p1") == "https://ikman.lk/p2"
