# Project 2: Movie Release Analysis

## Overview

Your team has been hired by a media company to understand social media
responses to three movies released in July 2026:

- _The Odyssey_
- _Spider-Man: Brand New Day_
- _Moana_ (live-action)

The company is especially interested in each movie's visibility and reception
relative to the other movies released around the same time. This analysis will
answer:

1. What aspect or topic of a movie is the focus of each post?
2. How much coverage did each movie receive relative to the other movies?

Conduct the analysis and submit a report discussing the findings.

## Analysis details

### Platform and data collection

Collect posts from a social media platform. Reddit no longer accepts new Data
API access requests, so use it only if your group already has working Reddit
API credentials. Otherwise, consider a platform with free access, such as:

- **Bluesky** — post search requires a free account and an app password.
- **YouTube** — comments can be collected through the YouTube Data API, which
  has a free daily quota.

Justify the platform choice in the report's **Data** section.

Collect **at least 500 posts total** across the three movies. Design the
collection procedure to avoid biasing coverage volume toward or against any
selected movie. Apply comparable time windows and collection/search procedures
to each movie. Explain the search and sampling procedure so the volume
comparisons are interpretable.

Set filters so that all collected posts have a very high likelihood of being
about one of the selected movies and are in English. Describe those filters and
any limitations in the report.

### Topic development and annotation

Use the post text and, when available, its title. You do not need to follow
links in posts.

1. Conduct open coding on **200 posts** to develop the topic categories.
2. Assign **exactly one topic** to each post.
3. Develop between **3 and 8 topics** in total.
4. After finalizing the topics, manually annotate the entire dataset of at least
   500 posts using the topic scheme.

Document the codebook and the annotation process in the report.
A team-ready starting point is in [the draft topic codebook](docs/topic-codebook-draft.md);
revise it after independently coding a shared pilot sample.

### Topic characterization

For each topic category:

- Calculate the **10 words with the highest TF-IDF scores**.
- Use an LLM (for example, ChatGPT, Claude, or Gemini) to write a representative
  summary of the category.
- Report the LLM/model used and the exact prompt supplied.

## Report

Discuss the findings, including the topics identified, the relative coverage
received by the selected movies, and the methods and limitations that affect
those comparisons. Include the platform justification, collection filters and
sampling procedure, topic codebook and annotation process, TF-IDF results, and
the LLM model and prompt.

## Bluesky collection scripts

The shared movie configuration is `data/movie_data.json`. Both collectors read
the release dates, search terms, and movie IDs from this file. The dataset
builder uses the same dates to filter release-week posts and selects **500 posts
total**: 167 for _The Odyssey_, 167 for _Spider-Man: Brand New Day_, and 166 for
_Moana_ (live-action). It also randomly selects 200 of those posts for open
coding, with 67 from each of the first two movies and 66 from _Moana_.

Install the collector dependencies:

```bash
python3 -m pip install atproto python-dotenv
```

Create a Bluesky **app password** from your account settings and set it with
your handle in a root `.env` file:

```text
BLUESKY_HANDLE=your-handle.bsky.social
BLUESKY_APP_PASSWORD=your-app-password
```

No separate Bluesky API key is used. Keep `.env` private and do not commit it.
Collect posts for the first seven days after each release:

```bash
python3 scripts/collect_release_week.py
```

To collect one movie, use its ID from `data/movie_data.json`, for example:

```bash
python3 scripts/collect_release_week.py --movie the_odyssey
```

The alternate `get_bluesky_posts.py` script searches a 30-day window from
7 days before to 22 days after each release, capped at 3,000 posts per movie.
The dataset builder expects the release-week files, not those alternate-window
files:

```bash
python3 scripts/build_movie_dataset.py
```

The builder uses different disambiguation cues for each title: _The Odyssey_
needs a film-related cue or associated filmmaker/cast, _Spider-Man: Brand New
Day_ accepts its full title and common title aliases, and _Moana_ needs a
live-action/remake/cast cue or a 2026 film-context cue. These rules prioritize
likely relevance, not sentiment; negative and positive opinions are both kept.
They are triage filters, so manually verify sampled posts before coding.

The builder first draws each movie's annotation quota, then removes only
feed-attribution-only posts and posts containing only standalone links. It
replaces these from that movie's remaining qualified pool and logs the
excluded/replacement URIs in `sampling_summary.json`. The 167/167/166 quotas
are for annotation, not coverage. Comparing the unique, human-screened
relevant-post counts from each movie's first seven days after its own release
is a defensible release-week (event-time) comparison. The windows are equal in
length but not the same calendar dates, so disclose that calendar events and
platform conditions may differ.
