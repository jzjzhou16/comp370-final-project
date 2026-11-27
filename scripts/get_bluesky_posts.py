import json, os
from datetime import datetime, timedelta
from atproto import Client
from dotenv import load_dotenv

# Setting up configs, paths, and Bluesky authentication
MAX_POSTS = 3000
PAGE_SIZE = 100

script_path = os.path.dirname(__file__)
data_path = os.path.join(script_path, "../data")
bluesky_data_path = os.path.join(data_path, "raw", "bluesky")

load_dotenv(os.path.join(script_path, "../.env"))

client = Client()
client.login(
    os.getenv("BLUESKY_HANDLE"),
    os.getenv("BLUESKY_APP_PASSWORD")
)

# Grab movie info
with open(os.path.join(data_path, "movie_data.json")) as f:
    movies = json.load(f)["movies"]


# Collect posts for each movie
for movie in movies:
    release = datetime.strptime(movie["release_date"], "%Y-%m-%d")

    # Collect posts from 7 days before to 21 days after release
    start_date = (release - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (release + timedelta(days=22)).strftime("%Y-%m-%d")

    params = {
        "q": movie.get("search_query", f'"{movie["movie_name"]}"'),
        "since": start_date,
        "until": end_date,
        "lang": "en",
        "sort": "latest",
        "limit": PAGE_SIZE
    }

    posts = []
    seen = set()
    cursor = None

    # Retrieve posts page by page until reach 3k limit
    while len(posts) < MAX_POSTS:
        if cursor:
            params["cursor"] = cursor

        response = client.app.bsky.feed.search_posts(params)

        # Skipping duplicates
        for post in response.posts:
            if post.uri not in seen:
                posts.append(post.model_dump(mode="json"))
                seen.add(post.uri)

            if len(posts) >= MAX_POSTS:
                break

        print(f"{movie['movie_name']}: {len(posts)} posts")

        # Continue to the next page
        new_cursor = response.cursor

        if not new_cursor or not response.posts or new_cursor == cursor:
            break

        cursor = new_cursor

    # Save collected posts
    os.makedirs(bluesky_data_path, exist_ok=True)
    output = os.path.join(bluesky_data_path, f"{movie['movie_id']}.json")

    with open(output, "w") as f:
        json.dump(posts, f, indent=4)

    print(f"Saved {len(posts)} posts for {movie['movie_name']}\n")