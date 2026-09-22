"""Command line entry point: discover | crawl | export | stats."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import logging
import sys

from .config import CrawlConfig, DEFAULT_CONFIG_PATH, RATNAPURA_TOWNS
from .crawl import Crawler
from .discover import run_discovery
from .export import to_csv, to_excel, to_jsonl
from .fetcher import Fetcher
from .store import Store
from .tabular import import_file, import_json_file, summarise, to_listing


def _load_config(args: argparse.Namespace) -> CrawlConfig:
    path = Path(args.config)
    config = CrawlConfig.load(path) if path.exists() else CrawlConfig()

    for attr in ("delay_seconds", "max_pages_per_query", "max_listings",
                 "locale", "district_slug", "user_agent"):
        value = getattr(args, attr, None)
        if value is not None:
            setattr(config, attr, value)
    if getattr(args, "categories", None):
        config.categories = args.categories
    if getattr(args, "no_details", False):
        config.fetch_detail_pages = False
    if getattr(args, "no_images", False):
        config.collect_images = False
    if getattr(args, "ignore_robots", False):
        config.obey_robots = False
    return config


def cmd_discover(args: argparse.Namespace) -> int:
    config = _load_config(args)
    report = run_discovery(config, report_path=args.report,
                           config_path=args.config,
                           cache_dir=None if args.no_cache else args.cache_dir)

    print("\n=== discovery report ===")
    print(json.dumps(
        {k: v for k, v in report.items() if k not in ("attempts", "config")},
        indent=2, ensure_ascii=False,
    ))
    if report.get("attempts"):
        print("\nURL attempts:")
        for attempt in report["attempts"]:
            print(f"  [{attempt.get('status')}] "
                  f"listings={attempt.get('listings', '-')} "
                  f"strategy={attempt.get('strategy', '-')} {attempt['url']}")
    print(f"\nFull report: {args.report}")
    return 0 if report.get("resolved") else 1


def cmd_crawl(args: argparse.Namespace) -> int:
    config = _load_config(args)
    if not Path(args.config).exists():
        print(f"note: {args.config} not found; using built-in defaults. "
              "Run 'discover' first for best results.\n", file=sys.stderr)

    with Store(args.db) as store, Fetcher(
        config, cache_dir=None if args.no_cache else args.cache_dir
    ) as fetcher:
        crawler = Crawler(config, store, fetcher, progress=lambda m: print(m, flush=True))
        if args.details_only:
            crawler.crawl_details()
        else:
            crawler.run()

        print("\n=== crawl finished ===")
        print(crawler.stats.summary())
        if crawler.stats.expanded:
            print(f"categories fanned out to town level: "
                  f"{', '.join(crawler.stats.expanded)}")
        print(f"fetcher: {fetcher.stats}")
        print(f"database: {args.db} ({store.count()} listings)")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        if store.count() == 0:
            print("nothing to export; the database is empty", file=sys.stderr)
            return 1
        out = Path(args.out)
        suffix = out.suffix.lower()
        if suffix == ".csv":
            n = to_csv(store, out, flatten=not args.no_flatten,
                       district=args.district)
        elif suffix in (".jsonl", ".json"):
            n = to_jsonl(store, out, district=args.district)
        elif suffix in (".xlsx", ".xlsm"):
            n = to_excel(store, out, flatten=not args.no_flatten,
                         district=args.district)
        else:
            print(f"unsupported output type '{suffix}'; "
                  "use .csv, .jsonl or .xlsx", file=sys.stderr)
            return 2
        print(f"wrote {n} listings to {out}")
    return 0


def cmd_import_table(args: argparse.Namespace) -> int:
    reader = import_json_file if str(args.path).lower().endswith(".json") else import_file
    rows, conflicts = reader(args.path)
    if not rows:
        print(f"no table rows found in {args.path}", file=sys.stderr)
        return 1

    if args.only_district:
        kept = [r for r in rows if r.district == args.only_district]
        print(f"filtering to district {args.only_district!r}: "
              f"keeping {len(kept)} of {len(rows)} rows")
    else:
        kept = rows

    with Store(args.db) as store:
        new, updated = store.upsert_many([to_listing(r) for r in kept])

    print(json.dumps(summarise(rows), indent=2, ensure_ascii=False))
    print(f"\nimported {new} new, {updated} merged into existing -> {args.db}")

    flagged = [r for r in kept if r.flags]
    if flagged:
        print(f"\n{len(flagged)} of {len(kept)} imported rows carry a data flag; "
              "see the 'Data flags' attribute column in the export.")
    if conflicts:
        print(f"{len(conflicts)} advert(s) appear with conflicting prices:")
        for conflict in conflicts:
            print(f"  {conflict['title'][:60]} -> "
                  f"{', '.join(conflict['variants'])}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        print(json.dumps(store.stats(), indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ikman-extract",
        description="Extract ikman.lk classified listings for Ratnapura district.",
        epilog="Typical run:  ikman-extract discover  &&  ikman-extract crawl  "
               "&&  ikman-extract export -o out/ratnapura.csv",
    )
    parser.add_argument("--db", default="data/ikman.sqlite", help="SQLite database path")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                        help="runtime config written by 'discover'")
    parser.add_argument("--cache-dir", default="cache",
                        help="cache fetched HTML here (makes re-parsing free)")
    parser.add_argument("--no-cache", action="store_true", help="disable the HTML cache")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_crawl_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("--delay-seconds", type=float, dest="delay_seconds",
                       help="minimum seconds between requests (default 1.5)")
        p.add_argument("--max-pages-per-query", type=int, dest="max_pages_per_query",
                       help="pagination cap per query (default 25)")
        p.add_argument("--max-listings", type=int, dest="max_listings",
                       help="stop after this many listings")
        p.add_argument("--locale", choices=["en", "si", "ta"], help="site language")
        p.add_argument("--district-slug", dest="district_slug",
                       help="override the district URL slug")
        p.add_argument("--user-agent", dest="user_agent")
        p.add_argument("--categories", nargs="+", help="restrict to these category slugs")
        p.add_argument("--no-details", action="store_true",
                       help="search pages only; skip per-advert detail pages")
        p.add_argument("--no-images", action="store_true", help="do not record image URLs")
        p.add_argument("--ignore-robots", action="store_true",
                       help="do not consult robots.txt (you take responsibility "
                            "for complying with the site's terms)")

    p_discover = sub.add_parser(
        "discover", help="probe the live site, resolve URLs/selectors, write config")
    p_discover.add_argument("--report", default="discover-report.json")
    add_crawl_opts(p_discover)
    p_discover.set_defaults(func=cmd_discover)

    p_crawl = sub.add_parser("crawl", help="crawl search results and advert pages")
    p_crawl.add_argument("--details-only", action="store_true",
                         help="only fetch detail pages still pending in the database")
    add_crawl_opts(p_crawl)
    p_crawl.set_defaults(func=cmd_crawl)

    p_export = sub.add_parser("export", help="write the database out to a file")
    p_export.add_argument("-o", "--out", default="out/ratnapura-ikman.csv",
                          help=".csv, .jsonl or .xlsx")
    p_export.add_argument("--no-flatten", action="store_true",
                          help="keep attributes as one JSON column")
    p_export.add_argument("--district",
                          help="export only listings resolved to this district")
    p_export.set_defaults(func=cmd_export)

    p_import = sub.add_parser(
        "import-table",
        help="import listings from the browser extractor's JSON or from "
             "Markdown tables")
    p_import.add_argument(
        "path",
        help="a .json payload from browser/ikman-extract.js, or a file of "
             "Markdown tables")
    p_import.add_argument("--only-district",
                          help="import only rows resolved to this district")
    p_import.set_defaults(func=cmd_import_table)

    p_stats = sub.add_parser("stats", help="summarise what has been collected")
    p_stats.set_defaults(func=cmd_stats)

    p_towns = sub.add_parser("towns", help="list the Ratnapura localities used for fan-out")
    p_towns.set_defaults(func=lambda a: (print("\n".join(RATNAPURA_TOWNS)), 0)[1])

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
