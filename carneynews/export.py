"""Human annotation exports; never change or overwrite human labels."""
import csv
import json
from pathlib import Path
import random
from .screening import RULE, screen


def safe_cell(value):
    value = "" if value is None else str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")):
        return "'" + value
    return value


def write_csv(path, fields, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: safe_cell(row.get(k, "")) for k in fields})


def export(store, directory, seed=370):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    articles = store.articles()
    annotation = []
    screening = [dict(a, **screen(a["title"], a["opening_text"])) for a in articles
                 if a["extraction_status"] == "extracted"]
    eligible = [a for a in screening if a["screening_hint"] != "no_subject_in_excerpt"]
    random.Random(seed).shuffle(eligible)
    for i, article in enumerate(eligible):
        annotation.append({"article_id": article["article_id"], "headline": article["title"],
                           "opening_text": article["opening_text"], "assigned_to": f"Person {(i % 4) + 1}",
                           "topic": "", "sentiment": "", "eligibility": "", "article_type": "",
                           "duplicate_of": "", "text_verified": "", "status": "not_started", "notes": "",
                           "screening_hint": article["screening_hint"], "screening_reason": article["screening_reason"]})
    write_csv(directory / "annotation.csv", ["article_id", "headline", "opening_text", "assigned_to", "topic",
              "sentiment", "eligibility", "article_type", "duplicate_of", "text_verified", "status", "notes",
              "screening_hint", "screening_reason"], annotation)
    # Everyone remains auditable; absent-subject cases move to a separate human screening queue.
    write_csv(directory / "screening.csv", ["article_id", "title", "opening_text", "screening_hint", "screening_reason", "eligibility"], screening)
    metadata = {s["domain"]: s for s in store.coverage()}
    manifest = [dict(a, **{"publisher": metadata[a["domain"]]["name"],
                          "publisher_country": metadata[a["domain"]]["country"],
                          "group": metadata[a["domain"]]["group"],
                          "rating": metadata[a["domain"]]["rating"],
                          "rating_url": metadata[a["domain"]]["rating_url"]}) for a in articles]
    write_csv(directory / "manifest.csv", ["article_id", "uuid", "url", "canonical_url", "publisher", "publisher_country",
              "published_at", "language", "group", "rating", "rating_url", "title", "description", "snippet",
              "extraction_status", "extraction_method", "extraction_note", "relevance_status"], manifest)
    write_csv(directory / "coverage.csv", ["domain", "name", "country", "group", "rating", "confidence", "rating_url",
              "articles", "extracted", "requests", "found", "next_page", "complete", "capped"], store.coverage())
    with (directory / "study.json").open("x", encoding="utf-8") as f:
        snapshot = store.db.execute("SELECT config FROM settings WHERE id=1").fetchone()[0]
        json.dump({"study": json.loads(snapshot), "assignment_seed": seed, "relevance_rule": RULE,
                   "note": "Candidate records only. Humans verify text, relevance, article type, and syndicated duplicates. "
                           "Outlet groups are external ratings, not article labels."}, f, indent=2)
    return len(annotation)
