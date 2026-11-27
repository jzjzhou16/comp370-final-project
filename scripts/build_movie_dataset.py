#!/usr/bin/env python3
"""Build a reproducible movie-discussion sample from full Bluesky JSON dumps.

Usage (from project root):
    python3 scripts/build_movie_dataset.py

Inputs:
    data/raw/bluesky_release_week/{the_odyssey,spider_man_brand_new_day,moana_live_action}.json
Outputs (only three files):
    data/processed/final_500_posts.tsv
    data/processed/open_coding_200.tsv
    data/processed/sampling_summary.json

Automatically filters likely movie-related posts; does NOT verify their relevance.
Film quotas are for topic annotation, NOT estimates of Bluesky visibility.
Uses only Python standard library (no pip install needed).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

SEED = 3702026
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOVIE_DATA_PATH = PROJECT_ROOT / "data" / "movie_data.json"
with MOVIE_DATA_PATH.open(encoding="utf-8") as file:
    MOVIE_DATA = json.load(file)["movies"]
MOVIES = {
    movie["movie_id"]: {
        "name": movie["movie_name"],
        "start": movie["release_date"],
        "end": (date.fromisoformat(movie["release_date"]) + timedelta(days=7)).isoformat(),
        "n": movie["sample_posts"],
        "open_n": movie["open_coding_posts"],
    }
    for movie in MOVIE_DATA
}
TOTAL_SELECTED = sum(movie["n"] for movie in MOVIES.values())
TOTAL_OPEN_CODING = sum(movie["open_n"] for movie in MOVIES.values())

# These rules prioritize precision, not exhaustive retrieval. Each movie gets
# its own combination of title aliases and disambiguating film-context cues.
ODYSSEY = re.compile(r"\b(?:the\s+)?odyssey\b", re.I)
ODYSSEY_FILM_CONTEXT = re.compile(
    r"\b(?:christopher\s+nolan|matt\s+damon|anne\s+hathaway|"
    r"tom\s+holland|zendaya|robert\s+pattinson|charlize\s+theron|"
    r"movie|film|trailer|teaser|premiere|screening|review|"
    r"letterboxd|tickets?|cinema|theat(?:er|re)s?|"
    r"release|opening\s+weekend|watched|watching|saw|loved|"
    r"hated|boring|amazing|disappointing|great|bad)\b", re.I
)
ODYSSEY_2026_TITLE = re.compile(r"\bodyssey\s*\(\s*2026\s*\)", re.I)
SPIDER_MAN_BRAND_NEW_DAY = re.compile(
    r"\bspider[-\s]?man\s*:?\s*brand\s+new\s+day\b|"
    r"\bspidermanbrandnewday\b|\bspidermanbnd\b|"
    r"\bbrand\s+new\s+day\s+(?:spider[-\s]?man|spiderman)\b|"
    r"\bspider[-\s]?man\s*(?:4|four)\b", re.I
)
SPIDER_MAN_FILM_CONTEXT = re.compile(
    r"\b(?:tom\s+holland|zendaya|sadie\s+sink|jon\s+bernthal|"
    r"marisa\s+tomei|trailer|teaser|premiere|screening|review|"
    r"letterboxd|tickets?|cinema|theat(?:er|re)s?|"
    r"release|opening\s+weekend|2026)\b", re.I
)
MOANA = re.compile(r"\bmoana\b", re.I)
MOANA_LIVE_ACTION_SIGNAL = re.compile(
    r"\b(?:live[-\s]?action|remake|catherine\s+laga['’]?aia|"
    r"thomas\s+kail|rena\s+owen|john\s+tui|frankie\s+adams)\b", re.I
)
MOANA_2026_FILM_CONTEXT = re.compile(
    r"\bmoana\b.{0,40}\b2026\b|\b2026\b.{0,40}\bmoana\b", re.I
)
MOANA_MOVIE_CONTEXT = re.compile(
    r"\b(?:movie|film|trailer|teaser|premiere|screening|review|"
    r"letterboxd|tickets?|cinema|theat(?:er|re)s?|release|"
    r"opening\s+weekend|watched|watching|saw|loved|hated)\b", re.I
)
FILM_REVIEW_TITLE = re.compile(r"\b(?:review\s+of|review:?)\b", re.I)
BARE_URL = re.compile(
    r"^(?:https?://|www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/\S*)?$", re.I
)
FEED_METADATA_LINE = re.compile(
    r"^(?:by|published(?:\s+on)?|date|source)\s*:", re.I
)


def preview(post):
    """Only reads previews already included in JSON, never accesses URLs."""
    for obj in (post.get("record", {}).get("embed"), post.get("embed")):
        if isinstance(obj, dict) and isinstance(obj.get("external"), dict):
            e = obj["external"]
            return str(e.get("title") or ""), str(e.get("description") or ""), str(e.get("uri") or "")
    return "", "", ""


def normalize(slug, post):
    record = post.get("record") or {}
    lang = record.get("langs") or []
    if not any(str(x).lower().startswith("en") for x in lang):
        return None
    date = str(record.get("created_at") or "")[:10]
    cfg = MOVIES[slug]
    if not cfg["start"] <= date < cfg["end"]:
        return None
    uri = str(post.get("uri") or "")
    body = str(record.get("text") or "").strip()
    if not uri or not body:
        return None
    title, description, link = preview(post)
    handle = str((post.get("author") or {}).get("handle") or "")
    # Bluesky links can use a DID in lieu of a handle.
    did = uri.split("/")[2] if uri.startswith("at://") else ""
    url = f"https://bsky.app/profile/{handle or did}/post/{uri.rsplit('/', 1)[-1]}"
    return {"movie_slug": slug, "movie": cfg["name"], "date_utc": date,
            "post_text": body, "embedded_title": title,
            "embedded_description": description, "embedded_url": link,
            "post_url": url, "uri": uri}


def relevant_rule(slug, row):
    """Return a rule-based reason for likely relevance, or '' if uncertain.

    Only explicit, high-confidence relevance evidence qualifies. Intentionally do not
    exclude negative reviews or posts with few likes.
    """
    body = row["post_text"]
    title = row["embedded_title"]
    desc = row["embedded_description"]
    combined = f"{body} {title} {desc}"
    if slug == "the_odyssey":
        if ODYSSEY.search(combined) and (
            ODYSSEY_FILM_CONTEXT.search(combined) or ODYSSEY_2026_TITLE.search(combined)
        ):
            return "odyssey_title_plus_film_context"
        if FILM_REVIEW_TITLE.search(title) and ODYSSEY.search(title):
            return "embedded_odyssey_review_title"
        return ""
    if slug == "spider_man_brand_new_day":
        if SPIDER_MAN_BRAND_NEW_DAY.search(combined):
            return "brand_new_day_title_alias"
        if (re.search(r"\bspider[-\s]?man\b", combined, re.I)
                and re.search(r"\b(?:bnd|4|four)\b", combined, re.I)
                and SPIDER_MAN_FILM_CONTEXT.search(combined)):
            return "spider_man_abbreviation_plus_film_context"
        if FILM_REVIEW_TITLE.search(title) and SPIDER_MAN_BRAND_NEW_DAY.search(title):
            return "embedded_spider_man_review_title"
        return ""
    if MOANA.search(combined):
        if MOANA_LIVE_ACTION_SIGNAL.search(combined):
            return "moana_title_plus_live_action_context"
        if (MOANA_2026_FILM_CONTEXT.search(combined)
                and MOANA_MOVIE_CONTEXT.search(combined)):
            return "moana_title_plus_2026_film_context"
    return ""


def non_substantive_reason(row):
    """Flag only feed attribution and standalone links without post commentary."""
    text = row["post_text"].strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and lines[0].lower().startswith("feed:"):
        metadata_only = all(
            FEED_METADATA_LINE.match(line) or all(
                BARE_URL.fullmatch(token.strip(".,!?()[]{}<>\"'"))
                for token in line.split()
            )
            for line in lines[1:]
        )
        if metadata_only:
            return "feed_attribution_only"

    tokens = text.split()
    if tokens and all(
        BARE_URL.fullmatch(token.strip(".,!?()[]{}<>\"'"))
        for token in tokens
    ):
        return "bare_link_only"
    return ""


def write_tsv(path: Path, fields: list[str], rows: list[dict]) -> None:
    """Write real TSV (tabs between columns, proper quoting for post text)."""
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=fields, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def daily_counts(rows: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter(r["date_utc"] for r in rows).items()))


def run(raw_dir: Path, out_dir: Path, seed: int) -> None:
    # STEP 1: Clean and filter every movie before exporting anything.
    matches_by_movie = {}
    report = {
        "random_seed": seed,
        "sampling_method": (
            "Deduplicate URI; require English metadata and correct seven-day release "
            "window; apply movie-specific high-precision relevance rules; "
            "draw each movie quota uniformly at random, exclude only feed-attribution-only "
            "and standalone-link posts, and replace exclusions from that movie's "
            "remaining qualified pool. "
            f"The {TOTAL_OPEN_CODING}-post open-coding subset is randomly drawn from the selected "
            f"{TOTAL_SELECTED} "
            "using fixed movie quotas."
        ),
        "sample_screen": {
            "excluded_reasons": [
                "feed_attribution_only",
                "bare_link_only",
            ],
            "other_non_substantive_or_irrelevant_posts": (
                "Not automatically excluded; review these during human relevance checks."
            ),
        },
        "total_selected": TOTAL_SELECTED,
        "total_open_coding": TOTAL_OPEN_CODING,
        "movies": {},
        "limitations": [
            "Rule-qualified means likely relevant, not human verified. Some false positives may remain.",
            "Keyword/context rules may miss valid indirect discussions and vary in recall by film.",
            "The near-equal 167/167/166 annotation quotas are deliberate; do not interpret them as relative movie coverage.",
            "Retrieved Bluesky search volume is not guaranteed to be exhaustive.",
            "Language is based on the API-provided language tag and may contain errors."
        ]
    }

    for slug, cfg in MOVIES.items():
        source = raw_dir / f"{slug}.json"
        if not source.is_file():
            raise FileNotFoundError(
                f"Full data file missing: {source} (a *_summary.json is not enough)"
            )
        posts = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(posts, list):
            raise ValueError(f"Expected a JSON list of posts in {source}")

        deduped = {}
        for post in posts:
            if not isinstance(post, dict):
                continue
            row = normalize(slug, post)
            if row is not None:
                deduped[row["uri"]] = row

        eligible = [deduped[uri] for uri in sorted(deduped)]
        hits = []
        for row in eligible:
            reason = relevant_rule(slug, row)
            if reason:
                hits.append({**row, "filter_reason": reason})
        if len(hits) < cfg["n"]:
            raise RuntimeError(
                f"{cfg['name']}: only {len(hits)} likely-relevant posts, "
                f"but {cfg['n']} needed. Please inspect filtering rules, "
                "rather than filling with unrelated posts."
            )

        matches_by_movie[slug] = hits
        report["movies"][slug] = {
            "name": cfg["name"],
            "window_start_inclusive_utc": cfg["start"],
            "window_end_exclusive_utc": cfg["end"],
            "raw_retrieved_posts": len(posts),
            "eligible_english_unique_posts": len(eligible),
            "rule_qualified_posts": len(hits),
            "selected_for_annotation": cfg["n"],
            "selected_for_open_coding": cfg["open_n"],
            "eligible_daily_counts": daily_counts(eligible),
            "rule_qualified_daily_counts": daily_counts(hits),
            "relevance_rule_counts": dict(sorted(Counter(p["filter_reason"] for p in hits).items())),
        }
        print(
            f"{cfg['name']}: raw {len(posts):,} | English/dated/unique {len(eligible):,} "
            f"| likely relevant {len(hits):,} | selecting {cfg['n']}"
        )

    # STEP 2: Sample each quota, then replace only obvious non-substantive posts.
    rng = random.Random(seed)
    selected = []
    for slug, cfg in MOVIES.items():
        hits = matches_by_movie[slug]
        # hits are ordered by URI (stable), so the seed makes sampling reproducible.
        initial = rng.sample(hits, cfg["n"])
        initial_uris = {row["uri"] for row in initial}
        kept = []
        excluded = []
        for row in initial:
            reason = non_substantive_reason(row)
            if reason:
                excluded.append((row, reason))
            else:
                kept.append(row)

        needed = cfg["n"] - len(kept)
        replacements_pool = [
            row for row in hits
            if row["uri"] not in initial_uris and not non_substantive_reason(row)
        ]
        if len(replacements_pool) < needed:
            raise RuntimeError(
                f"{cfg['name']}: {needed} substantive replacement posts needed, "
                f"but only {len(replacements_pool)} remain in the qualified pool."
            )
        replacements = rng.sample(replacements_pool, needed)
        sample = kept + replacements
        selected.extend(sample)
        movie_report = report["movies"][slug]
        movie_report["initial_sampled"] = len(initial)
        movie_report["excluded_non_substantive"] = len(excluded)
        movie_report["replacement_count"] = len(replacements)
        movie_report["replacements"] = [
            {
                "excluded_uri": row["uri"],
                "reason": reason,
                "replacement_uri": replacement["uri"],
                "replacement_date_utc": replacement["date_utc"],
            }
            for (row, reason), replacement in zip(excluded, replacements)
        ]
        movie_report["selected_daily_counts"] = daily_counts(sample)

    # Detect duplicate URI across movies if the queried release periods ever overlap.
    if len({p["uri"] for p in selected}) != TOTAL_SELECTED:
        raise RuntimeError("Same post selected twice across films. Inspect overlapping URIs.")

    rng.shuffle(selected)
    final = [
        {
            "post_id": f"P{i:04d}",
            "movie": row["movie"],
            "date_utc": row["date_utc"],
            "post_text": row["post_text"],
            "post_url": row["post_url"],
            "uri": row["uri"],
            "filter_reason": row["filter_reason"],
            "relevance_check": "",  # optional Y/N flag during team review
            "topic_code": "",  # filled in manually by your teammates
        }
        for i, row in enumerate(selected, start=1)
    ]

    # STEP 3: Draw the open-coding subset from the final sample.
    open_coding = []
    for slug, cfg in MOVIES.items():
        pool = [row for row in final if row["movie"] == cfg["name"]]
        open_coding.extend(rng.sample(pool, cfg["open_n"]))
    rng.shuffle(open_coding)

    assert len(final) == TOTAL_SELECTED and len(open_coding) == TOTAL_OPEN_CODING
    assert len({p["uri"] for p in open_coding}) == TOTAL_OPEN_CODING
    assert {p["uri"] for p in open_coding}.issubset({p["uri"] for p in final})

    # STEP 4: Save exactly two TSVs plus a JSON summary.
    fields = ["post_id", "movie", "date_utc", "post_text", "post_url",
              "uri", "filter_reason", "relevance_check", "topic_code"]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(out_dir / "final_500_posts.tsv", fields, final)
    write_tsv(out_dir / "open_coding_200.tsv", fields, open_coding)
    (out_dir / "sampling_summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print("\nSaved three files in:", out_dir)
    print(f"  final_500_posts.tsv     {TOTAL_SELECTED} screened posts for annotation")
    print("  open_coding_200.tsv     200 of those candidates for open coding")
    print("  sampling_summary.json   Counts, rules and limitations")
    print("\nNote: selected posts still require human relevance checks during annotation.")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir", type=Path, default=project_root / "data/raw/bluesky_release_week",
        help="Directory holding the three full movie JSON dumps",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=project_root / "data/processed",
        help="Directory where exactly three output files are created",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    run(args.raw_dir, args.out_dir, args.seed)


if __name__ == "__main__":
    main()
