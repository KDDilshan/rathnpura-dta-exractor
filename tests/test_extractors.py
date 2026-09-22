import pytest

from ikman.extractors import (
    JsonLdExtractor, LinkHeuristicExtractor, SelectorExtractor, StateBlobExtractor,
    extract_detail_page, extract_search_page, find_next_page,
)

DETAIL_URL = "https://ikman.lk/en/ad/toyota-axio-2015-for-sale-ratnapura-4f2a11"


@pytest.mark.parametrize("fixture,expected_strategy", [
    ("serp_jsonld", "json-ld"),
    ("serp_state", "state-blob"),
    ("serp_cards", "selectors"),
    ("serp_obfuscated", "link-heuristic"),
])
def test_each_page_shape_is_extracted_by_its_strategy(
    fixture, expected_strategy, fixture_html, serp_url
):
    listings, strategy = extract_search_page(fixture_html(fixture), serp_url)
    assert strategy == expected_strategy
    assert len(listings) == 2
    assert all(l.url.startswith("https://ikman.lk/en/ad/") for l in listings)
    assert all(l.title for l in listings)


def test_jsonld_reads_price_condition_and_location(fixture_html, serp_url):
    listings, _ = extract_search_page(fixture_html("serp_jsonld"), serp_url)
    axio = next(l for l in listings if "Axio" in l.title)
    assert axio.price_value == 8750000.0
    assert axio.currency == "LKR"
    assert (axio.town, axio.district) == ("Pelmadulla", "Ratnapura")
    assert axio.condition == "Used"
    assert axio.image_urls == ["https://i.ikman-st.com/axio/620/1.jpg"]


def test_state_blob_reads_numeric_and_nested_prices(fixture_html, serp_url):
    listings, _ = extract_search_page(fixture_html("serp_state"), serp_url)
    by_title = {l.title: l for l in listings}
    assert by_title["iPhone 13 Pro 256GB"].price_value == 218000.0
    assert by_title["iPhone 13 Pro 256GB"].is_promoted is True
    assert by_title["Dairy cows for sale"].price_value == 185000.0
    assert by_title["Dairy cows for sale"].town == "Kalawana"


def test_state_blob_keeps_unmapped_scalars_as_attributes(fixture_html, serp_url):
    listings, _ = extract_search_page(fixture_html("serp_state"), serp_url)
    phone = next(l for l in listings if "iPhone" in l.title)
    assert phone.attributes.get("adSourceType") == "member"
    assert phone.attributes.get("id") == 9911


def test_selector_strategy_reads_price_qualifier_and_promotion(fixture_html, serp_url):
    listings, _ = extract_search_page(fixture_html("serp_cards"), serp_url)
    by_title = {l.title: l for l in listings}
    dio = by_title["Honda Dio 2019"]
    assert (dio.price_value, dio.price_qualifier) == (385000.0, "Negotiable")
    assert dio.town == "Eheliyagoda"
    assert by_title["House for rent"].price_qualifier == "Per Month"
    assert by_title["House for rent"].is_promoted is True


def test_heuristic_ignores_non_advert_links(fixture_html, serp_url):
    """The obfuscated fixture also contains /en/help and a pager link."""
    listings = LinkHeuristicExtractor().search_page(
        fixture_html("serp_obfuscated"), serp_url
    )
    urls = {l.url for l in listings}
    assert urls == {
        "https://ikman.lk/en/ad/gem-cutting-machine-ratnapura-ee5503",
        "https://ikman.lk/en/ad/driver-vacancy-embilipitiya-ff9927",
    }


def test_heuristic_survives_unknown_class_names(fixture_html, serp_url):
    """Selector strategy is blind to the obfuscated markup; heuristic is not."""
    assert SelectorExtractor().search_page(fixture_html("serp_obfuscated"), serp_url) == []
    assert len(LinkHeuristicExtractor().search_page(
        fixture_html("serp_obfuscated"), serp_url)) == 2


def test_detail_page_yields_attributes_and_breadcrumbs(fixture_html):
    listing = extract_detail_page(fixture_html("detail"), DETAIL_URL)
    assert listing.title == "Toyota Axio 2015"
    assert listing.price_value == 8750000.0
    assert listing.price_qualifier == "Negotiable"
    assert (listing.category, listing.subcategory) == ("Vehicles", "Cars")
    assert listing.condition == "Used"
    assert listing.attributes["Mileage"] == "98,000 km"
    assert listing.attributes["Year of Manufacture"] == "2015"
    assert listing.attributes["Transmission"] == "Automatic"
    assert len(listing.image_urls) == 2
    assert "full service history" in listing.description


@pytest.mark.parametrize("fixture", [
    "serp_jsonld", "serp_state", "serp_cards", "serp_obfuscated",
])
def test_next_page_found_in_every_shape(fixture, fixture_html, serp_url):
    assert find_next_page(fixture_html(fixture), serp_url) == \
        "https://ikman.lk/en/ads/ratnapura?page=2"


def test_next_page_absent_on_last_page(serp_url):
    assert find_next_page("<html><body>no pager</body></html>", serp_url) is None


def test_next_page_follows_numeric_pager_from_current_page():
    html = '<a href="/en/ads/ratnapura?page=4">4</a><a href="/en/ads/ratnapura?page=9">9</a>'
    assert find_next_page(html, "https://ikman.lk/en/ads/ratnapura?page=3") == \
        "https://ikman.lk/en/ads/ratnapura?page=4"


def test_empty_and_malformed_html_are_safe(serp_url):
    for html in ["", "<html>", "not html at all", "<script>{bad json}</script>"]:
        listings, strategy = extract_search_page(html, serp_url)
        assert listings == []
        assert strategy == "none"


def test_extractors_do_not_capture_non_ad_urls():
    html = '<a href="/en/ads/ratnapura/cars">Cars</a><a href="/en/ad/real-ad-x1">Ad</a>'
    listings = LinkHeuristicExtractor().search_page(html, "https://ikman.lk/en/ads/ratnapura")
    assert [l.url for l in listings] == ["https://ikman.lk/en/ad/real-ad-x1"]
