"""Run with python3 -m carneynews. No third-party packages required."""
import argparse
from datetime import datetime, timezone
import os
import math
from pathlib import Path
import sqlite3
import sys
import time

from . import config as study_config
from .api import APIError, fetch_page
from .collect import collect
from .export import export
from .extract import fetch_openings, reextract_saved
from .diagnostics import diagnose
from .store import Store

ROOT = Path(__file__).resolve().parents[1]


def local_token():
    if "THE_NEWS_API_TOKEN" in os.environ:
        return os.environ["THE_NEWS_API_TOKEN"].strip()
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "THE_NEWS_API_TOKEN":
                return value.strip().strip("\"'")
    return ""


def print_coverage(store):
    rows = store.coverage()
    print(f"{'Outlet':24} {'Group':7} {'Records':>7} {'Openings':>8} {'Requests':>8}  Search")
    groups = {"left": 0, "center": 0, "right": 0, "unrated": 0}
    openings = dict.fromkeys(groups, 0)
    for row in rows:
        state = "CAPPED: incomplete" if row["capped"] else "exhausted" if row["complete"] else f"next page {row['next_page']}"
        print(f"{row['name']:24} {row['group']:7} {row['articles']:7} {row['extracted']:8} {row['requests']:8}  {state}")
        groups[row["group"]] += row["articles"]
        openings[row["group"]] += row["extracted"]
    print(f"\nSaved records: {sum(r['articles'] for r in rows)}; extracted candidates: {sum(r['extracted'] for r in rows)}")
    print("Group counts: " + ", ".join(f"{key}={value}" for key, value in groups.items()))
    print("Extracted by group: " + ", ".join(f"{key}={value}" for key, value in openings.items()))
    if not openings["left"] or not openings["right"]:
        print("Coverage gap: usable openings from both left and right have not yet been obtained.")
    print("Records still require human relevance, text, article-type, and syndicated-duplicate checks.")


def parser():
    result = argparse.ArgumentParser(description="Collect Mark Carney news and prepare human annotation files.")
    result.add_argument("--config", type=Path, default=ROOT / "config/north-america.json")
    result.add_argument("--data", type=Path, default=ROOT / "data-premiership-20")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Show study and sources without network access or data writes")
    download = sub.add_parser("collect", help="Collect/resume TheNewsAPI metadata and raw responses")
    download.add_argument("--max-requests", type=int, default=90)
    download.add_argument("--daily-limit", type=int, default=90)
    download.add_argument("--request-interval", type=float, default=3.1, help="Seconds between API requests (default 3.1)")
    download.add_argument("--domains", help="Optionally target configured outlets, comma-separated")
    sub.add_parser("status", help="Show saved outlet and perspective coverage")
    fetch = sub.add_parser("fetch", help="Fetch accessible publisher openings, honoring robots rules")
    fetch.add_argument("--limit", type=int, default=20)
    fetch.add_argument("--retry-failed", action="store_true")
    sub.add_parser("reextract", help="Clean saved HTML offline; preserve original exports")
    diagnostic = sub.add_parser("diagnose", help="Compare study/name/domain searches without changing article checkpoints")
    diagnostic.add_argument("--domains", help="Comma-separated domains from the study config")
    diagnostic.add_argument("--max-requests", type=int, default=8)
    diagnostic.add_argument("--daily-limit", type=int, default=90)
    diagnostic.add_argument("--request-interval", type=float, default=3.1)
    spreadsheet = sub.add_parser("export", help="Create a NEW export folder; never overwrite annotation work")
    spreadsheet.add_argument("--output", type=Path)
    spreadsheet.add_argument("--seed", type=int, default=370)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    store = None
    try:
        config = study_config.load(args.config)
        if args.command == "plan":
            print(f"Query: {config['query']}\nLanguage: {config['language']}\nDates: {config['start']} through {config['end']} (UTC)")
            print(f"Page size: {config['page_size']}; rotate across every source before returning to one.")
            sampling = config.get("sampling")
            if sampling:
                print(f"Target: {sampling['target_outlets']} usable outlets x "
                      f"{sampling['articles_per_outlet']} usable articles; "
                      f"{sampling['candidate_pool_per_outlet']} candidates/outlet before screening.")
                print("If outlets fall short after screening, redistribute their quotas to Canadian outlets first, "
                      "then US outlets if needed.")
                print(f"Fallback policy (manual): for a shortfall outlet, use its "
                      f"{sampling['articles_per_outlet']} most recent "
                      "candidates and record its out-of-window dates and exclusions.")
            for source in config["sources"]:
                print(f"  {source['group']:6} {source['name']:24} {source['domain']} ({source['rating']})")
            print("\nExternal outlet ratings do not determine article sentiment. Check source coverage with a pilot.")
            return 0
        token = None
        if args.command in {"collect", "diagnose"}:
            if not math.isfinite(args.request_interval) or args.request_interval < 0:
                raise ValueError("request-interval must be finite and nonnegative")
            token = local_token()
            if not token:
                raise ValueError("Set THE_NEWS_API_TOKEN in your environment or local .env file. See .env.example.")
        if args.command in {"status", "fetch", "export", "reextract"} and not (args.data / "collection.sqlite").exists():
            raise ValueError("No collection exists yet. Run collect after configuring your token.")
        store = Store(args.data, config)
        if args.command in {"collect", "diagnose"}:
            last_call = [0.0]
            def request_with_config(probe_config, source, page=1):
                delay = max(0, last_call[0] + args.request_interval - time.monotonic())
                if delay:
                    time.sleep(delay)
                last_call[0] = time.monotonic()
                return fetch_page(probe_config, source, page, token)
            if args.command == "diagnose":
                domains = args.domains.split(",") if args.domains else None
                diagnose(store, config, request_with_config, domains=domains,
                         max_requests=args.max_requests, daily_limit=args.daily_limit,
                         on_result=lambda d, p, n: print(f"{d}: {p}={n}", flush=True))
                print(f"Diagnostic responses saved in {args.data / 'diagnostics'}; collection checkpoints unchanged.")
            else:
                result = collect(store, config, lambda s, p: request_with_config(config, s, p),
                                 args.max_requests, args.daily_limit,
                                 on_page=lambda s, p, n: print(f"{s['domain']} page {p}: {n} returned", flush=True),
                                 domains=[d.strip() for d in args.domains.split(",")] if args.domains else None)
                print(f"This run used {result['requests']} requests. Re-run the same command to resume.")
                print_coverage(store)
        elif args.command == "fetch":
            count = fetch_openings(store, args.limit, args.retry_failed,
                                   on_article=lambda article_id: print(f"Processed {article_id}", flush=True))
            print(f"Processed {count} publisher pages.")
            print_coverage(store)
        elif args.command == "status":
            print_coverage(store)
        elif args.command == "reextract":
            print(f"Reprocessed {reextract_saved(store)} saved pages without network requests.")
        elif args.command == "export":
            output = args.output or ROOT / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            count = export(store, output, args.seed)
            print(f"Exported {count} extracted candidates for human review to {output}")
        return 0
    except (APIError, ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped. Saved progress is retained; re-run to resume.", file=sys.stderr)
        return 130
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
