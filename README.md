# Mark Carney news collection

Collect news matching `"Mark Carney" | "Carney government"` through TheNewsAPI,
save original API responses, fetch accessible article openings, and export files
for four human annotators. Requires **Python 3.11+**; no packages to install.

## Current version and source coverage

The default study is now `config/north-america.json`: **20 selected outlets**
(10 Canadian, 10 US), chosen from a 47-outlet availability screen, with data
stored in `data-premiership-20/`. The common study window is **March 14, 2025–
November 25, 2026**, from Mark Carney's swearing-in as Prime Minister through
the chosen end date. The selected outlets have initial query matches and include
four left-rated and four right-rated sources; the rest are unrated. Mexico
outlets are not in the target country set. The target is **20 usable Canadian/US
outlets × 25 usable articles**.

The API reported fewer than 25 matches for two selected sources in this window:
New York Times (7) and Washington Post (8). Thus, 500 articles at an equal
25-per-outlet quota cannot be reached with the current query/window, even before
extraction failures, relevance checks, article-type exclusions, and duplicate
removal. Check a broader candidate query and inspect returned records before
committing to this sample design. The source frame includes national
broadcasters, newspapers, regional
papers, wire reporting, business outlets, and independent reporting. This is a
broad English-language source frame, not a claim to include every major North
American outlet. French/Spanish coverage requires a separate language protocol.
Sources without a verified political rating are `unrated`, never assumed center.

The intended workflow is to collect up to 50 candidates per outlet for the
common window, check article relevance, article type, extraction quality, and
syndicated duplicates, then randomly select 25 eligible articles per selected
outlet using the recorded seed (370). The current application does not enforce
the 50-candidate pool or automatically select the final 25; export prepares the
candidate review sheets and shuffles annotation assignments. If an outlet
cannot supply enough candidates in the common window, the
configured fallback policy is to use its **25 most recent candidates**. This
is a manual protocol step: the collector does not automatically expand an
outlet's date range. Record the actual dates and mark those records as fallback
when collecting them. Screen those 25 before calling the outlet usable; replace
it if fewer than 25 pass the agreed exclusions. The target means 500 usable
articles after exclusions, not 500 API records. The fallback is a documented
exception to the common-period comparison, not evidence that periods are
equivalent. The config records the target and fallback policy; availability
checks and human screening still determine which outlets actually qualify.

The configured quota starts at 25 per outlet. If screening leaves an outlet
with fewer than 25 eligible unique articles, include its eligible articles and
redistribute the shortfall as evenly as possible among Canadian outlets with
remaining eligible candidates; only if they cannot absorb it should US outlets
receive the remainder. This makes the final sample Canada-weighted beyond the
baseline quota. Report per-outlet counts and do not describe the overall result
as equally weighted by outlet.

The original six-source pilot is preserved. To inspect/reprocess it explicitly:

```bash
python3 -m carneynews --config config/study.json --data data status
python3 -m carneynews --config config/study.json --data data reextract
python3 -m carneynews --config config/study.json --data data export
```

Source control is explicit: edit the `sources` list in a NEW config and select
it with `--config` and a NEW `--data` directory. `domains` is sent per request.
There is no guarantee that the provider indexes a configured outlet or that its
publisher allows extraction. The status report now counts extracted openings by
political group, so merely listing left/right sources cannot satisfy coverage.

To target an already configured source while retaining the full study frame:

```bash
python3 -m carneynews collect --domains nbcnews.com,washingtonpost.com --max-requests 6
```

Targeted requests are recorded normally; explain deliberate oversampling in your
methods. Publisher aliases are explicitly allowlisted: ABC's API source remains
`abcnews.go.com`, while article URLs on the publisher-confirmed `abcnews.com`
domain are accepted. Other off-source URLs remain rejected.

Use a small diagnostic for zero-result sources:

```bash
python3 -m carneynews diagnose --domains cbc.ca,nbcnews.com --max-requests 8
```

Each source costs up to four requests: the study query, a broader `Carney` query,
a no-keyword domain control, and a no-keyword `www` domain control. All retain the
same language and date window. Results go to the selected data directory's
`diagnostics/`; article page checkpoints stay unchanged. Zero in a control means
no articles returned for that domain/window/language, not proof that an outlet
published no coverage. If the provider cannot supply left sources, use another
authorized provider/archive and document that collection change rather than
silently substituting right-only data.

API calls are now spaced by 3.1 seconds by default. If your account is still
rate-limited, respect the reported delay and resume more slowly:

```bash
python3 -m carneynews collect --max-requests 20 --request-interval 6
```

Request counters are per data directory, while your provider quota is account-wide.
Subtract requests used in other studies/clients when setting the daily cap.

## Relevance screening and clean text

The adopted rule is:

> Include an article when its headline and standardized opening make Carney's
> actions, statements, leadership, reputation, or a policy explicitly attributed
> to him a substantive focus. He may share the focus with another person.
> Exclude passing mentions, background references, and unrelated recommendations.

The script implements a **human screening workflow**, not an automated semantic
judge. `priority_review` means the surname appears in the headline or early lead;
`needs_focus_review` means a less clear/background mention; `no_subject_in_excerpt`
means the cleaned headline/opening has no standalone Carney reference.

Every extracted record remains in **screening.csv** with its reason and a blank
human `eligibility` field. `annotation.csv` initially holds the first two groups,
with topic/sentiment/eligibility left blank. The third group is held for screening,
not deleted or labeled neutral. Humans can restore a held record if it satisfies
the agreed rule (for example, an unambiguous reference by role). Record that
decision before final sampling. API descriptions are not used as a substitute
for the standardized opening when deciding relevance.

Standalone link-only recommendation paragraphs are removed before taking the
first 150 words, including when their text is embedded in JSON-LD articleBody.
Inline citation links and uppercase quotations are preserved. This cleaning is
separate from relevance screening: a Carney-focused article can contain an
unrelated recommendation. Site-specific/manual review is still necessary.
`reextract` refreshes saved HTML offline without replacing previous export files.

## Quick start

Run these commands from this repository:

```bash
python3 -m carneynews plan
```

Create a free account at [TheNewsAPI](https://www.thenewsapi.com/register). Copy
`.env.example` to `.env` using your editor and paste the token after
`THE_NEWS_API_TOKEN=`. Alternatively, set that environment variable locally.
Never paste tokens into chat, commit them, or put them in the study config.

Start with **20 requests**, one for each selected outlet (up to 60 returned records):

```bash
python3 -m carneynews collect --max-requests 20
python3 -m carneynews status
python3 -m carneynews fetch --limit 40
python3 -m carneynews export
```

Inspect coverage and opening text before scaling up:

```bash
python3 -m carneynews collect --max-requests 40
python3 -m carneynews fetch --limit 100
python3 -m carneynews export
```

Repeat collection on later days and extraction as needed. The collector resumes
automatically, including request usage already recorded that UTC day. `export`
creates a new timestamped folder each time; import ONE final annotation CSV into
Google Sheets once collection and text checks are finished. Re-exporting does
not merge or preserve edits made outside this application: the original export
folder is left untouched. Do not replace your working sheet with a fresh export.

## Original pilot source selection

The original six-source pilot in `config/study.json` uses **October 1–November
24, 2026, UTC**, inclusive by date (the API's start/end boundary semantics may
exclude exact midnight records). The expanded default in
`config/north-america.json` proposes the 2025 common period described above.
Searches cover title and main text. There is no topic or sentiment keyword filter.
Search matches are candidates: humans must exclude incidental mentions,
non-news/opinion pieces if outside the agreed protocol, unusable text, and
syndicated copies.

`config/study.json` preserves the original pilot protocol and six-source list;
the expanded default is `config/north-america.json`. Ratings were checked
on **November 25, 2026** and are external outlet-level judgments, not factuality
ratings, article sentiment, or evidence that Canadian/US political scales match.

| Collection group | Outlets | AllSides rating |
|---|---|---|
| Left | [CBC](https://www.allsides.com/news-source/cbc-news-media-bias), [CNN Digital](https://www.allsides.com/news-source/cnn-media-bias) | Lean Left |
| Right | [National Post](https://www.allsides.com/news-source/national-post-media-bias), [Fox News Digital](https://www.allsides.com/news-source/fox-news-media-bias) | Lean Right; Right |
| Center | [Globe and Mail](https://www.allsides.com/news-source/globe-and-mail-media-bias), [Toronto Star](https://www.allsides.com/news-source/toronto-star-media-bias) | Center |

AllSides reports low/initial confidence for these Canadian outlet ratings;
CNN's rating has high confidence and Fox's medium. Toronto Star is deliberately
recorded as **Center according to this particular rating source**, even though
other frameworks may classify it differently. The team should assess and approve
the selection and document this limitation before substantive comparisons.

Requests rotate across outlets, so a high-volume source cannot consume the whole
budget first. This means equal collection opportunity, **not equal article
counts, a representative estimate of all North American news, or predetermined
sentiment balance**. Country and outlet are confounded in this small source list;
avoid interpreting group differences as causal effects of ideology.

Coverage reports include sources with zero records, extraction shortfalls, and
unfinished/capped searches. A configured outlet is not proof of actual coverage.
Do not claim balanced coverage or 500 usable articles until counts and human
checks support it. Add sources or widen the period only as a documented protocol
revision, with a new data directory.

```bash
python3 -m carneynews --config config/study.json --data data-revised plan
```

## What is saved

```text
data-premiership-20/collection.sqlite Article records, checkpoints, local request accounting
data-premiership-20/raw/*.json         Original API response snapshots
data-premiership-20/pages/*.html       Retrieved publisher pages for extraction review
exports/<timestamp>/
  annotation.csv            Candidates with subject mentions, four-person assignments, blank labels
  screening.csv             All extracted candidates, including held incidental/absent-subject cases
  manifest.csv              IDs, URLs, outlet metadata, ratings, snippets, extraction status
  coverage.csv              Every outlet's counts, requests, and search progress
  study.json                Protocol snapshot and assignment seed
```

Data, exports, credentials, and caches are ignored by Git. Raw JSON stores no
request URL or API token. HTTP error messages omit token-bearing URLs. Never
share the local `.env` file. Ordinary file permissions apply to downloaded data.

Tracking parameters and URL fragments are removed for URL deduplication. IDs
remain stable across runs. Similar stories, updated URLs, and cross-outlet wire
copies are **not automatically declared duplicates**; annotators use
`duplicate_of` after review. Raw API pages retain repeated records for provenance.

## Publisher text and access limitations

TheNewsAPI returns metadata and a short snippet, not full article text. The
`fetch` command checks publisher robots rules, spaces requests by at least two
seconds per domain, honors crawl-delay up to 60 seconds, and skips disallowed or
unverifiable access. It does not log in, bypass paywalls, or execute JavaScript.
Only article-marked HTML paragraphs or Article structured data are accepted.
This intentionally conservative extractor will miss some site layouts.

The opening is the **first 150 whitespace-separated words of extracted text**,
or the available shorter text. A different length requires a documented protocol
change. Only candidates with at least 20 extracted words appear in annotation.csv;
this threshold does not establish relevance, completeness, or correct extraction.
Humans must compare against the original and set `text_verified`. Missing, blocked,
paid, or unrecognized pages are recorded as `needs_manual`, not silently treated
as usable articles. Use authorized library access for these if available; do not
drop an entire political group just because its pages are harder to extract.

Failed pages stay skipped unless you explicitly retry:

```bash
python3 -m carneynews fetch --limit 20 --retry-failed
```

## Annotation workflow

Upload `annotation.csv` to a shared sheet; keep `manifest.csv` separately with the
coordinator to reduce outlet-rating cues during coding. Headlines can still
reveal their source, so this is not a fully blind study. Files use UTF-8 with BOM
and quote cells that could be interpreted as spreadsheet formulas.

1. Four people manually open-code 200 distinct articles; discuss and define 3–8 topics.
2. Calibrate topic and sentiment rules on a small independently coded pilot.
3. Freeze the codebook and label all final articles, including the initial 200.
4. Assignments are seeded and shuffled across the annotation queue, then distributed
   round-robin to Person 1–4 (counts differ by at most one). Replace placeholders
   with names. These assignments are not a statistical sampling procedure.
5. Screen inclusion first. Use dropdowns for agreed topics, Positive/Negative/Neutral, and annotation status.
   Leave labels blank until a human decides. Track eligibility, article type,
   duplicates, text verification, and ambiguous cases before final inclusion.
6. Freeze/export the reviewed sheet as CSV for later analysis. This collector
   never creates labels, topic definitions, or conclusions.

The screening CSV contains **all extracted candidates**, not a preselected 500-item sample.
After exclusions, verify at least 500 unique eligible articles. If there are more,
document your sampling procedure before annotation; do not just take the first 500.

## Quotas, pagination, and reproducibility

The [free plan](https://www.thenewsapi.com/pricing) currently advertises 100
requests/day and 3 articles/request. Defaults leave a buffer: 90 requests per run
and per UTC day. `--daily-limit` changes the local cap, not the provider's quota.
All attempted requests count locally, including failures; usage from another
script/account client is unknown. Account-level 402/429 responses stop the run
without advancing that page. There are no hidden retries that burn quota.

The response's actual limit determines pagination. A fixed study/config snapshot
prevents accidental mixing of queries and date ranges. Searches at the API's
20,000-result ceiling are reported capped/incomplete. Split the study's date
windows into separate documented collections if that occurs. API indexing may
change while collecting: fixed dates and archived responses improve auditability
but do not guarantee a static census.

Run one collector process per data directory. Successful pages checkpoint after
validation; a crash or failed request leaves the page retryable. A crash after an
HTTP response but before checkpointing may repeat a request; stable URL IDs prevent
duplicate rows. Account quotas reset according to the provider; the local counter
uses UTC calendar dates conservatively.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests are offline and use controlled API/HTML fixtures. Live collection requires
your local API token and network access. Passing tests do not establish publisher
availability or guarantee 500 eligible articles.

API reference: [TheNewsAPI documentation](https://www.thenewsapi.com/documentation).
