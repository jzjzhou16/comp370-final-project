# Relevance screening and North American source coverage

User approved adding substantive-focus screening, fixing related-story contamination,
checking left-source extraction, and broadening the source selection.

## Decisions

- The policy is recorded verbatim in `carneynews/screening.py`. Heuristics prioritize
  review; they do not assign final eligibility, topics, or sentiment.
- Preserve every extracted candidate in screening.csv. No-Carney excerpts are
  held out of topic annotation, not erased. Both co-subject and primary-subject
  articles can proceed after human confirmation.
- Detect standalone link-only recommendations from HTML structure and remove their
  exact normalized text from structured article bodies before taking 150 words.
  Keep inline citations and uppercase quotations. Verify against the pilot archives.
- Add a 47-outlet English-language catalogue: 20 Canadian, 25 US, two Mexican.
  This is a broad candidate frame, not an exhaustive universe of North American
  outlets. French and Spanish need a separate annotation-language protocol.
- Keep unrated sources explicitly unrated instead of inventing ideology labels.
- Preserve the original six-source study and its data. Expanded study uses
  config/north-america.json and data-north-america by default. Existing exports
  are never overwritten. Config changes always require a separate data directory.
- Diagnose study search, broad surname search, bare-domain control, and www-domain
  control separately. Archive responses and account for attempts without advancing
  article pagination. Each data directory counts local usage; provider quota remains
  account-wide, so be conservative when running multiple studies on the same day.

## Verification

- [x] Regression test reproduced embedded related-story contamination, then passed after fix.
- [x] Tests cover co-subject lead, government attribution, incidental/absent mention,
  surname substring, background cue, blank human labels, and separate screening queue.
- [x] Diagnostics tests preserve article checkpoints and count every probe.
- [x] Original pilot reprocessed from archived HTML without publisher requests.
- [x] Expanded live API pilot and left-source extraction result recorded.
- [x] Full final test run, source coverage report, and documentation verified.

## Execution evidence

- All 47 outlets received a successful first-page API response. Fifty records
  were saved from 17 outlets; pagination is deliberately incomplete for the pilot.
- An 18-page publisher extraction pilot produced ten openings, including two
  from left-rated NBC, five from right-rated sources, and three from unrated sources.
- CBC diagnostic: study, broader name, no-keyword bare-domain, and no-keyword
  www-domain controls each returned zero for the fixed English/date window.
  This does not establish that CBC published no relevant articles.
- API 429 response halted collection with checkpoints intact. Added configurable
  request spacing and safe Retry-After reporting, then resumed at six-second intervals.
- ABC source metadata used abcnews.go.com while returned article URLs used
  abcnews.com. Confirmed the publisher redirect, added a strict alias allowlist,
  and accepted the archived page without spending another API call.
- Original pilot exports preserved. Offline cleaning removed both identified
  related-story recommendations; the old pilot's four openings now produce one
  annotation candidate and three held screening records. Human labels remain blank.
- Targeted --domains collection supports retrying a source or checking left-source
  availability without changing the study frame or bypassing request accounting.
- All 39 offline tests pass. Live API/publisher availability is reported separately
  from test success. No final human relevance/topic/sentiment labels were assigned.
