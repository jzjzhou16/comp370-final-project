"""Collect Bluesky search results for the first seven UTC days of each film.

Run from the repository: python scripts/collect_release_week.py
Optional: --movie the_odyssey (or another movie_id from data/movie_data.json).
Completed daily files are reused on restart. No per-movie post cap is imposed.
Search results are candidates, not verified movie-related posts or a full census.
"""
import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

from atproto import Client
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "raw" / "bluesky_release_week"
PAGE_SIZE = 100
MAX_ATTEMPTS = 4


def save_json(path, data):
    """Write atomically so an interrupted write is not a completed checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def collect_day(client, movie_name, day, search_query=None):
    tomorrow = day + timedelta(days=1)
    params = {
        "q": search_query or f'"{movie_name}"',
        "since": f"{day.isoformat()}T00:00:00Z",
        "until": f"{tomorrow.isoformat()}T00:00:00Z",
        "lang": "en",
        "sort": "latest",
        "limit": PAGE_SIZE,
    }
    posts = {}
    cursors = set()
    page = 0
    while True:
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = client.app.bsky.feed.search_posts(params)
                break
            except Exception as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    raise RuntimeError(f"Collection failed for {movie_name}, {day}; day not marked complete.") from exc
                delay = 2 ** (attempt + 1)
                print(f"Request failed ({type(exc).__name__}); retrying in {delay}s", flush=True)
                time.sleep(delay)
        page += 1
        for post in response.posts:
            posts[post.uri] = post.model_dump(mode="json")
        print(f"{movie_name} | {day} | page {page}: {len(response.posts)} returned, {len(posts)} unique total", flush=True)
        cursor = response.cursor
        if not cursor:
            break
        if cursor in cursors:
            raise RuntimeError(f"Repeated cursor for {movie_name}, {day}; day not marked complete.")
        cursors.add(cursor)
        params["cursor"] = cursor
        time.sleep(0.5)
    return list(posts.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--movie", help="Collect only this movie_id (default: all movies)")
    args = parser.parse_args()
    with (ROOT / "data" / "movie_data.json").open(encoding="utf-8") as f:
        movies = json.load(f)["movies"]
    if args.movie:
        movies = [m for m in movies if m["movie_id"] == args.movie]
        if not movies:
            parser.error("Unknown movie_id; check data/movie_data.json")
    load_dotenv(ROOT / ".env")
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        raise SystemExit("Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD in the root .env file.")
    client = Client()
    client.login(handle, password)
    for movie in movies:
        name = movie["movie_name"]
        movie_id = movie["movie_id"]
        release = date.fromisoformat(movie["release_date"])
        all_posts = {}
        daily_counts = {}
        for offset in range(7):
            day = release + timedelta(days=offset)
            path = OUTPUT / movie_id / f"{day.isoformat()}.json"
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    daily_posts = json.load(f)
                print(f"Loading completed day: {name} | {day}", flush=True)
            else:
                daily_posts = collect_day(client, name, day, movie.get("search_query"))
                save_json(path, daily_posts)
                print(f"Saved completed day: {path.name}", flush=True)
            daily_counts[day.isoformat()] = len(daily_posts)
            for post in daily_posts:
                all_posts[post["uri"]] = post
        final_path = OUTPUT / f"{movie_id}.json"
        save_json(final_path, list(all_posts.values()))
        summary = {
            "movie": name,
            "since_inclusive_utc": release.isoformat() + "T00:00:00Z",
            "until_exclusive_utc": (release + timedelta(days=7)).isoformat() + "T00:00:00Z",
            "daily_retrieved_counts": daily_counts,
            "unique_retrieved_posts": len(all_posts),
            "note": "Raw search candidates; pagination ended normally for each saved day, not proof of exhaustive coverage.",
        }
        save_json(OUTPUT / f"{movie_id}_summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)
        print(f"Saved combined data: {final_path}", flush=True)
    print("Requested collections finished.")


if __name__ == "__main__":
    main()
