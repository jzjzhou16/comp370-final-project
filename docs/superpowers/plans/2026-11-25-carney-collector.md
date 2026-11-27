# Carney news collector implementation plan

**Goal:** Collect reproducible Mark Carney news search results from TheNewsAPI, representing left, center, and right outlet selections, and prepare human annotation files.

**Architecture:** Python command-line application with a JSON study configuration, SQLite checkpoints and request accounting, immutable raw response files, optional publisher opening extraction, and CSV exports. No runtime dependencies outside Python 3.11+.

**Spec:** The user's approved roadmap and request to begin development in this repository.

## Constraints and decisions

- Work in the user-selected folder; preserve existing files. No automatic commits or remote writes.
- Fixed UTC window: October 1 through November 24, 2026. Search `"Mark Carney" | "Carney government"` against title and main text.
- Six explicitly configured North American outlets: two left-leaning, two right-leaning, two center-rated. Preserve external rating provenance and confidence; never infer article sentiment from outlet rating.
- Rotate requests across sources and retain completion/shortfall counts. This balances collection effort, not article counts or sentiment.
- Default page size 3, request budget 90 per run and UTC day; all attempts count locally, including failures. Other API users are outside this accounting.
- JSON snapshots preserve API responses; SQLite checkpoints advance only with successfully validated responses. Resuming must not duplicate articles or lose a page after an error.
- Export labels blank and never overwrite an existing annotation CSV. Raw source metadata belongs in a separate manifest to permit blind coding.
- Snippets do not count as extracted openings. Only publisher text extracted from article markup/Article structured data is eligible for an opening; human verification remains required.
- Publisher extraction honors robots rules, does not bypass access controls, and records every failure. Use a consistent first 150 words from extracted text, not a fabricated summary.

## Review focus

1. A quota or network failure must preserve progress and keep tokens out of logs/files.
2. Low-volume sources must remain visible in coverage reports, including zero results.
3. Pagination must honor the server's actual limit and mark capped searches incomplete.
4. Tracking URLs must not create duplicate article IDs; syndicated copies remain reviewable.
5. Spreadsheet exports must resist formula interpretation and preserve previously annotated files.

## Tasks

- [x] Add failing offline tests for config validation, request construction, resumable collection, quota failures, deduplication, and annotation exports.
- [x] Implement `carneynews/config.py`, `api.py`, `store.py`, `collect.py`, and `export.py`; run `python3 -m unittest discover -s tests -v`.
- [x] Add failing tests for publisher parsing, robots handling, and extraction status. Implement `carneynews/extract.py`.
- [x] Add CLI commands `plan`, `collect`, `status`, `fetch`, and `export`, source provenance, configuration, and setup documentation.
- [x] Verify full offline suite, CLI smoke tests, and secret/git hygiene. Live collection requires a user-supplied local API token; do not claim live collection without it.

## Execution record

- Repository inspected: clean starter with only a README; no AGENTS.md found.
- Ruling: use the requested folder directly and execute the accepted workflow inline; no additional design approval or subagent work is needed for this initial collector.
- All 25 offline tests pass, including publication-window/language validation and sanitized HTTP errors. CLI `plan` and `--help` smoke checks pass.
- Author review: data and credentials stay ignored; no remote writes, automatic commits, or live API calls were made. Live provider and publisher availability remains unverified until a token is configured.
