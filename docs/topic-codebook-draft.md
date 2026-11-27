# Draft Topic Codebook

This draft is based on the 200-post open-coding subset in
`data/processed/open_coding_200.tsv` (67 posts for *The Odyssey*, 67 for
*Spider-Man: Brand New Day*, and 66 for live-action *Moana*). The team will 
review and revise it after independently coding the annotation example. 

## Coding unit and evidence

- Code one Bluesky post as one unit. Assign exactly one topic.
- Use the post text and any title or description already included with the
  post. Do not follow links or infer their contents.
- Code the aspect that is the main focus, not every aspect mentioned.
- A positive, negative, or mixed opinion can belong to any topic.

## Topic categories

| Code | Topic | Include when the main focus is... | Examples observed in the sample |
|---|---|---|---|
| NAR | Narrative, themes, and adaptation | Plot, pacing, structure, ending, themes, source material, mythology, or how the film adapts an earlier work. | Discussion of Nolan's changes to Homer's story; criticism of the remake's script or faithfulness to the animated original. |
| CHAR | Characters, performances, and casting | A character's portrayal or arc, acting, chemistry, casting choices, or a specific character relationship. | Reactions to a performer's role, Peter Parker's characterization, or the portrayal of a supporting character. |
| CRAFT | Film craft and spectacle | Visuals, cinematography, editing, sound, music, effects, action, runtime, or a distinctive theatrical/format experience such as IMAX or 4DX. | Praise for scenery or performances' presentation; a comment focused on the film's IMAX or 4DX experience. |
| REACT | Overall evaluation and recommendation | A broad rating, general praise or criticism, or whether the author recommends seeing the film, without a more specific aspect being the main focus. | A short “great movie” reaction, a star rating with no detail, or a general recommendation. |
| BIZ | Box office, exhibition, and industry strategy | Grosses, budgets, opening performance, ticket availability, theater attendance, censorship/distribution, marketing, or studio decisions and remake strategy. | Discussion of opening-weekend numbers, sold-out screenings, or whether Disney should have made a live-action remake. |
| FANDOM | Franchise, fandom, and fan activity | Franchise comparisons, fan theories, shipping, memes, merchandise, fan expectations, or audience/fandom behavior. Use this when the post centers on fan culture rather than the film's social or political meaning. | Discussion of a new character pairing, franchise rankings, or fan response to a reveal. |
| CULT | Cultural, social, and political discourse | Political or religious readings, representation, identity, culture-war arguments, or broader social claims prompted by the film. | Debate over whether the film is “woke,” its religious/political message, or social arguments about its casting. |

## Decision rules for one topic

1. Identify the post's main claim or the aspect receiving the most detail.
2. Prefer the specific film aspect over a broad verdict: a post mainly about
   pacing is NAR even if it also says the film is good or bad.
3. Use BIZ when commercial performance, exhibition, or studio strategy is the
   point; use FANDOM for fan practices and franchise speculation; use CULT for
   social, political, religious, or identity arguments.
4. If a post has a broad opinion but no specific focus, use REACT.
5. If several aspects receive similar attention, use the aspect emphasized in
   the opening or conclusion. If still tied, discuss it during adjudication and
   record the agreed reason.
6. Do not infer a topic from a movie title, hashtag, account name, or link alone.

## Codability screening and replacements

The builder automatically removes only two clear cases from the initial
per-movie sample: feed-attribution metadata with no commentary, and posts
consisting only of URL(s). It replaces each from the remaining qualified
candidates for that same movie and records the excluded/replacement URIs and
reason in `sampling_summary.json`. This preserves each movie's 167/167/166
quota. Run the builder again to reproduce the sample; do not hand-edit a
generated TSV and then rerun it, since that will overwrite those files.

- Other uncertain cases, including bare attendance updates or potentially
  unrelated posts, still need human review. Keep a log with post ID, decision,
  and reason; replace only when the team agrees it cannot be coded or is
  irrelevant.
- Do not replace a post just because it is short, negative, positive, critical,
  or not interesting. A concise general reaction can be coded REACT.
- If human review requires additional replacements, draw from the remaining
  qualified candidates for the same movie, record the seed and both post IDs,
  and keep the original/replacement log. Do not silently substitute posts.
- The screen is for the 500-post annotation dataset. Coverage counts should be
  calculated from the full retrieved pool with a documented relevance rule,
  not from the balanced 500-post sample.

## Team pilot and adjudication

1. Have all four team members independently code the same 25–40 posts, sampled
   across all three films.
2. Compare disagreements, clarify category boundaries, and revise this draft.
3. Independently code a second shared subset after revisions. Keep the agreed
   codebook version and a disagreement/adjudication log.
4. Divide the remaining annotation work among the team. Discuss unclear cases
   and apply the same final rules consistently.

## Coverage is a separate measure

The 167/167/166 quotas in the annotation dataset are balanced for analysis; they
do not measure which film received more attention. Comparing each film's first
seven days after its own release is defensible as a release-relative or
event-time comparison: it asks how much attention each received during its
launch week. These are equal-length windows, not the same calendar dates, so
state that the comparison does not control for differences in calendar events
or platform conditions. Report the exact window and unique, human-screened
relevant counts for each film, and disclose API/search limits and the
possibility that title filters have different precision and recall.
