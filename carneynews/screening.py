"""Transparent screening hints; final inclusion and coding remain human decisions."""
import re

RULE = ("Include an article when its headline and standardized opening make Carney's actions, "
        "statements, leadership, reputation, or a policy explicitly attributed to him a substantive focus. "
        "He may share the focus with another person. Exclude passing mentions, background references, "
        "and unrelated recommendations.")
SUBJECT = re.compile(r"\b(?:mark\s+)?carney(?:['’]s)?\b", re.I)
BACKGROUND = re.compile(r"\b(?:for context|previously|background|last year|historically|in passing)\b", re.I)


def screen(headline, opening):
    """Prioritize obvious lead mentions without pretending to solve semantic centrality."""
    headline, opening = headline or "", opening or ""
    matches = list(SUBJECT.finditer(opening))
    if not SUBJECT.search(headline) and not matches:
        hint, reason = "no_subject_in_excerpt", "No standalone Carney reference in the cleaned headline/opening; screen before coding."
    elif SUBJECT.search(headline):
        hint, reason = "priority_review", "Carney appears in the headline; confirm substantive focus and article type."
    elif matches and len(opening[:matches[0].start()].split()) < 60 and not BACKGROUND.search(opening[:matches[0].end()]):
        hint, reason = "priority_review", "Carney appears early in the opening; confirm substantive or shared focus."
    else:
        hint, reason = "needs_focus_review", "Carney appears in the opening but centrality is unclear or the wording suggests background."
    return {"screening_hint": hint, "screening_reason": reason, "eligibility": ""}
