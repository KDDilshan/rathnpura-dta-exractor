# rathnpura-dta-exractor

Extracts classified-advert data from [ikman.lk](https://ikman.lk) for Sri Lanka's
**Ratnapura district** (Sabaragamuwa Province) into SQLite, CSV, JSONL or Excel.

Collects every advert it can reach across all categories — vehicles, property,
electronics, jobs, animals, services and the rest — with per-category facets
(mileage, bedrooms, brand, …) preserved rather than flattened away.

---

## Before you start: read this

**The live site was unreachable when this code was written.** It was developed in
an environment whose network policy blocks `ikman.lk`, so the exact HTML,
URL slugs and API shape could not be inspected. Two consequences:

1. **Nothing here is hardcoded to guessed markup.** Parsing runs four strategies
   in parallel and keeps whichever works (see [How parsing survives](#how-parsing-survives-a-site-redesign)).
   The last one keys only on the advert URL pattern, so it returns rows even if
   every CSS class on the site changes.
2. **Run `discover` first.** It probes the real site and writes down what it
   actually found — the district slug, URL template, working strategy, real
   category slugs and card selectors. Everything the offline build had to guess
   is settled there by observation.

```bash
ikman-extract discover      # resolve the real structure, write data/config.json
```

If `discover` reports `listings: 0` on a `200` response, the search page is
rendered client-side and the HTTP-only path cannot see it; see
[Troubleshooting](#troubleshooting).

### Terms of use

This is a scraper pointed at a site you do not own. Before running it at scale:

- Check `https://ikman.lk/robots.txt` and ikman's terms of service, and satisfy
  yourself that your intended use is permitted. **This tool does not make that
  judgement for you.**
- `robots.txt` is obeyed by default, including any `Crawl-delay`. If it cannot
  be read, the crawler refuses rather than assuming permission. `--ignore-robots`
  exists, and using it puts compliance entirely on you.
- Defaults are deliberately slow — one request per ~1.5 s, single-threaded.
  Please don't raise that just because you can.
- **Advert contact details are not collected.** ikman puts phone numbers behind
  a separate reveal action; this tool never calls it. Harvesting personal
  contact data carries obligations under Sri Lanka's Personal Data Protection
  Act No. 9 of 2022 that a scraper cannot discharge for you. Listing text is
  seller-authored and may still contain personal information — treat the output
  accordingly, and don't republish it.

---

## Install

```bash
git clone https://github.com/KDDilshan/rathnpura-dta-exractor.git
cd rathnpura-dta-exractor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                  # optional: provides the `ikman-extract` command
pip install openpyxl              # optional: .xlsx export
```

Python 3.9+. Without `pip install -e .`, substitute `python3 -m ikman.cli` for
`ikman-extract` in every command below.

## Usage

```bash
ikman-extract discover                          # 1. probe the site, write config
ikman-extract crawl                             # 2. collect everything (resumable)
ikman-extract export -o out/ratnapura.csv       # 3. write it out
ikman-extract stats                             # what have I got?
```

Start small to confirm it works before committing to a full run:

```bash
ikman-extract crawl --max-listings 50 --categories vehicles --no-details
```

### Useful options

| Option | Effect |
| --- | --- |
| `--max-listings N` | stop after N adverts |
| `--categories vehicles property` | restrict to certain categories |
| `--no-details` | search pages only; much faster, less detail |
| `--delay-seconds 3` | be slower / gentler |
| `--max-pages-per-query N` | pagination cap per query (default 25) |
| `--locale si` | crawl the Sinhala site (`en`, `si`, `ta`) |
| `--details-only` | fetch only the detail pages still pending |
| `--no-cache` | don't cache fetched HTML |
| `--ignore-robots` | skip the robots.txt check (your responsibility) |

Export format follows the extension: `.csv`, `.jsonl` or `.xlsx`.

### Resuming

Interrupt with `Ctrl-C` and re-run the same `crawl` command. Visited pages and
completed adverts are recorded in SQLite, so a resumed run picks up where it
stopped instead of starting over. Fetched HTML is also cached under `cache/`,
which makes re-parsing free — useful when you improve a parser and want to
re-extract without re-downloading.

---

## How it gets *all* the data

Search pagination on ikman is capped, so a single "everything in Ratnapura"
query silently truncates — you get the first few hundred adverts and no
indication that more exist.

The crawler works a frontier of `(location, category)` queries instead. When a
query **saturates** — runs to the page cap and is still finding adverts — that
category is re-asked town by town across the district's 25 localities, reaching
the listings the capped query hid. Queries that finish before the cap are never
expanded, so the request budget stays proportional to how much data actually
exists rather than to the size of the town list.

Listings from every query are merged by advert URL, so the overlap between a
district-wide query and its town-level re-asks costs storage, not duplicates.

## How parsing survives a site redesign

Four strategies run against every page; the one returning the most (and most
complete) listings wins, per page:

| Strategy | Reads | Breaks when |
| --- | --- | --- |
| `json-ld` | `<script type="application/ld+json">` schema.org markup | the site drops SEO markup |
| `state-blob` | the JS hydration payload (`window.initialData` and friends) | the payload is removed |
| `selectors` | CSS selectors, including any learned by `discover` | class names change |
| `link-heuristic` | advert anchors found by URL shape, reading their card | advert URLs stop looking like `/en/ad/<slug>` |

Learned selectors have their CSS-module build hash stripped
(`normal-ad--1Vc3D` → `normal-ad`), so they survive the deploys that rotate
those hashes. The `extracted_by` column records which strategy produced each
row, so you can see at a glance whether you're on a solid path or the fallback.

Search-page and detail-page reads of the same advert are **merged, not
replaced** — each knows things the other doesn't, and a re-crawl never blanks a
field that was previously populated.

## Output

One row per advert. Fixed columns plus `attr_*` columns flattened from each
category's own facets:

```
listing_id, url, title, price_text, price_value, currency, price_qualifier,
category, subcategory, location_text, town, district, description, condition,
seller_name, seller_type, is_promoted, posted_text, posted_at, image_urls,
source_page, extracted_by, scraped_at, attr_brand, attr_mileage, ...
```

Notes:

- `price_value` is numeric for sorting; `price_text` keeps the original. Adverts
  reading "Ask for price" get a null value and a `price_qualifier` instead, so
  "free", "negotiable" and "price withheld" stay distinguishable.
- `posted_at` normalises ikman's relative stamps ("2 days ago") to ISO-8601 UTC,
  computed at scrape time; `posted_text` keeps the original wording.
- `town` / `district` are split from the location label. `Ratnapura` names both
  a town and the district, and the town is kept specific.
- CSV is written UTF-8 with a BOM so Sinhala and Tamil text opens correctly in
  Excel. Use `--no-flatten` to keep facets in one JSON column.

Query the SQLite file directly for anything ad-hoc:

```sql
SELECT town, category, COUNT(*), ROUND(AVG(price_value))
FROM listings WHERE price_value > 0
GROUP BY town, category ORDER BY 3 DESC;
```

---

## Getting the data when the crawler cannot reach ikman

`browser/ikman-extract.js` runs in **your** browser, on ikman.lk, and walks
every page of the current search from inside the page. Same-origin `fetch` is
allowed there, so it needs no proxy, no credentials and no scraping
infrastructure — useful when the machine running the crawler cannot reach the
site.

1. Open the search you want, e.g. `https://ikman.lk/en/ads/ratnapura/land-for-sale`
2. Open DevTools (**F12**), go to **Console**. If it refuses pasted code, type
   `allow pasting` first.
3. Paste the whole file, press Enter, wait. It prints progress per page.
4. A `.json` file downloads when it finishes.

```bash
ikman-extract --db data/listings.sqlite import-table ikman-....json
ikman-extract --db data/listings.sqlite export -o out/land.csv --district Ratnapura
```

`import-table` detects a `.json` payload and reads it through the same
normalisation and audit as the Markdown path.

It uses the same layered strategies as the Python extractors (JSON-LD, the
hydration payload, then advert-anchor cards) and merges all three per page, so a
field any one of them saw is kept. It pauses 1.2 s between pages, stops on the
first non-200, stops when a page yields nothing new, and caps at 100 pages. It
reads only pages you could click to yourself and never touches contact details
or the "show phone number" action.

**Records from this route carry the advert URL**, which is authoritative
identity — so unlike a Markdown paste, two different plots with the same title,
size and price stay separate rows, and re-importing is exactly idempotent.

## Importing a browser/manual extraction

If you collected listings another way — a browser extraction, a copy-paste, an
LLM reading the page — `import-table` ingests Markdown tables into the same
database and export pipeline:

```bash
ikman-extract --db data/listings.sqlite import-table data/raw/pasted-listings.md
ikman-extract --db data/listings.sqlite export -o out/ratnapura-land.csv --district Ratnapura
```

It copes with what such extractions actually look like: several tables
concatenated with **different column orders**, aliased headers (`Size` /
`Land Size` / `Extent`), titles containing unescaped `|`, sizes mixing perches
and acres, and prices quoted per-perch, per-acre or as a total. Everything is
normalised to `Size (perches)`, `Price per perch` and `Total price`, with the
original text kept alongside.

### It audits rather than trusts

Two fields in this data are demonstrably unreliable, so the importer flags them
instead of silently correcting:

- **Location.** ikman's location facet is the *seller's* choice, not the
  advert's town. A seller who advertises nationwide leaves it on one district
  while the advert is for a town elsewhere. The importer resolves the town named
  in the **title** against a district gazetteer (`ikman/gazetteer.py`, Sinhala
  place names included) and flags `location-mismatch:listed-X-actually-Y` on
  every disagreement. Towns not in the gazetteer are reported
  `district-unverified` rather than guessed.
- **Price basis.** The same advert appears as `Rs 200,000 / perch` in one paste
  and `Rs 2,000,000 / perch` in another — a 10× difference from reading a total
  as a rate. Adverts are grouped by title+size and any whose implied total sits
  more than 3× from the group median is flagged
  `price-conflicts-with-duplicate`.

Other flags: `per-perch-implausibly-low/high`, `per-perch-high-for-district`,
`total-implausibly-high`, `size-unit-conflicts-with-title`,
`price-basis-unstated`, `size-unparsed`. All land in the `attr_data_flags`
column, so you can filter on them in Excel.

Town spellings are canonicalised across scripts and variants
(`Rathnapura`, `රත්නපුර` → `Ratnapura`; `Abilipitiya`, `ඇඹිලිපිටිය` →
`Embilipitiya`), because otherwise one town splits into several groups and every
per-town aggregate is wrong.

Rows are de-duplicated on title+size+price, so re-importing the same paste is
idempotent.

## Project layout

```
ikman/
  config.py      site URLs, Ratnapura towns, category seeds, runtime knobs
  models.py      the Listing record and its merge semantics
  parsing.py     price / relative-date / location normalisation
  extractors.py  the four extraction strategies and page-shape scoring
  fetcher.py     robots.txt gate, rate limiting, retries, HTML cache
  store.py       SQLite persistence, upsert-merge, resume bookkeeping
  discover.py    probes the live site and writes what it found
  crawl.py       frontier, pagination, adaptive town fan-out
  export.py      CSV / JSONL / Excel
  gazetteer.py   Sri Lankan town -> district lookup, for auditing locations
  tabular.py     Markdown-table import, unit normalisation, data audit
  cli.py         discover | crawl | import-table | export | stats | towns
browser/         ikman-extract.js - in-browser extractor (see above)
tests/           135 tests, no network required
```

## Tests

```bash
pip install pytest && python3 -m pytest -q
```

135 tests, all offline. Fixtures cover all four page shapes, and the crawl tests
run the real `Crawler` end to end against an in-memory fake site, covering
pagination, resume, the saturation fan-out, detail merging and error handling. The importer tests
cover unit conversion, the location audit and the price-conflict detection.

## Troubleshooting

**`discover` resolves nothing** — check the `attempts` list in
`discover-report.json`:

- `403` / `429` — the site refused the request. Slow down (`--delay-seconds 5`).
- `200` with `listings: 0` — the page is rendered client-side, so there is
  nothing in the HTML to parse. Options: check `state_blob` in the report for a
  hydration payload; look for a JSON endpoint in your browser's network tab and
  point `search_path_template` at it; or drive a real browser with Playwright
  and feed its HTML to `extract_search_page`.
- `robots-disallowed` — robots.txt forbids the path for this user agent, or it
  could not be read at all.

**Crawl finds far fewer adverts than the site claims** — the page cap is biting
before the fan-out triggers. Lower `--max-pages-per-query` so saturation is
detected sooner, which makes the crawler fan out to town level earlier.

**Parsing worked and then stopped** — the site changed. Re-run `discover`; if
`extracted_by` has dropped to `link-heuristic`, the richer sources are gone and
row detail will be thinner until the selectors are relearned.
