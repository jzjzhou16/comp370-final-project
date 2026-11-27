"""Durable study state, raw response provenance, and stable article identities."""
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .api import utc_now
from .config import validate

# Publisher-confirmed domain migration (abcnews.go.com redirects to abcnews.com).
PUBLISHER_ALIASES = {"abcnews.go.com": ("abcnews.com",)}


def canonical_url(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    if parts.scheme not in {"http", "https"} or not host or parts.username or parts.port not in {None, 80, 443}:
        raise ValueError("Invalid article URL")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}]
    return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


def matches_domain(url, domain):
    host = (urlsplit(url).hostname or "").lower()
    return host == domain or host.endswith("." + domain)


def matches_publisher(url, domain):
    return any(matches_domain(url, allowed) for allowed in (domain, *PUBLISHER_ALIASES.get(domain, ())))


class Store:
    def __init__(self, directory, config):
        validate(config)
        self.config = config
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "raw").mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.directory / "collection.sqlite", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, config TEXT);
            CREATE TABLE IF NOT EXISTS sources (
                domain TEXT PRIMARY KEY, position INTEGER, metadata TEXT,
                next_page INTEGER DEFAULT 1, complete INTEGER DEFAULT 0,
                found INTEGER, capped INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY, domain TEXT, page INTEGER, day TEXT,
                created_at TEXT, status TEXT, error TEXT, raw_path TEXT);
            CREATE TABLE IF NOT EXISTS articles (
                article_id TEXT PRIMARY KEY, canonical_url TEXT UNIQUE, domain TEXT,
                record TEXT, extraction_status TEXT DEFAULT 'pending', opening_text TEXT DEFAULT '',
                extraction_method TEXT DEFAULT '', extraction_note TEXT DEFAULT '',
                extracted_at TEXT DEFAULT '');
        """)
        snapshot = json.dumps(config, sort_keys=True)
        previous = self.db.execute("SELECT config FROM settings WHERE id=1").fetchone()
        if previous and previous[0] != snapshot:
            self.db.close()
            raise ValueError("Study config changed. Use a new --data directory to preserve provenance.")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO settings VALUES (1, ?)", (snapshot,))
            for i, source in enumerate(config["sources"]):
                self.db.execute("INSERT OR IGNORE INTO sources(domain,position,metadata) VALUES(?,?,?)",
                                (source["domain"], i, json.dumps(source)))

    def close(self):
        self.db.close()

    def requests_today(self, day):
        return self.db.execute("SELECT count(*) FROM requests WHERE day=?", (day,)).fetchone()[0]

    def next_source(self, domains=None):
        selected = " AND s.domain IN (" + ",".join("?" for _ in domains) + ")" if domains else ""
        row = self.db.execute("""SELECT s.* FROM sources s
            LEFT JOIN requests r ON s.domain=r.domain WHERE s.complete=0 AND s.capped=0""" + selected + """
            GROUP BY s.domain ORDER BY count(r.id), s.position LIMIT 1""", domains or []).fetchone()
        return dict(row) if row else None

    def reserve_request(self, domain, page, day, daily_limit):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.requests_today(day) >= daily_limit:
                self.db.rollback()
                return None
            request_id = self.db.execute(
                "INSERT INTO requests(domain,page,day,created_at,status) VALUES(?,?,?,?, 'pending')",
                (domain, page, day, utc_now())).lastrowid
            self.db.commit()
            return request_id
        except Exception:
            self.db.rollback()
            raise

    def fail_request(self, request_id, error):
        with self.db:
            self.db.execute("UPDATE requests SET status='failed',error=? WHERE id=?", (error, request_id))

    def save_page(self, request_id, source, page, payload):
        # Preserve server data before parsing, even when validation subsequently fails.
        path = self.directory / "raw" / f"{request_id:06d}-{source['domain']}-page-{page:05d}.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved["response"] != payload or saved["source"] != source["domain"] or saved["page"] != page:
                raise ValueError("Archived response differs; refusing to overwrite it")
        else:
            with path.open("x", encoding="utf-8") as f:
                json.dump({"collected_at": utc_now(), "source": source["domain"], "page": page,
                           "response": payload}, f, ensure_ascii=False, indent=2)
        rows, meta = payload.get("data"), payload.get("meta")
        if not isinstance(rows, list) or not isinstance(meta, dict):
            raise ValueError("Malformed API response: expected data list and meta object")
        actual_limit, found = meta.get("limit"), meta.get("found")
        if not isinstance(actual_limit, int) or actual_limit < 1 or not isinstance(found, int) or found < 0:
            raise ValueError("Malformed API pagination metadata")
        if len(rows) > actual_limit or meta.get("returned") != len(rows):
            raise ValueError("API returned count does not match response")
        normalized = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("title") or not row.get("published_at"):
                raise ValueError("Article lacks title or publication date")
            published = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
            if published.tzinfo is None:
                raise ValueError("Publication timestamp lacks timezone")
            published_date = published.astimezone(timezone.utc).date().isoformat()
            if not self.config["start"] <= published_date <= self.config["end"]:
                raise ValueError("Article is outside the study window; raw response preserved")
            if row.get("language") not in self.config["language"].split(","):
                raise ValueError("Article language is outside the study protocol; raw response preserved")
            url = canonical_url(row.get("url", ""))
            if not matches_publisher(url, source["domain"]) or not matches_domain("https://" + str(row.get("source", "")), source["domain"]):
                raise ValueError("Article does not match requested source; raw response preserved")
            article_id = "MC" + hashlib.sha256(url.encode()).hexdigest()[:16]
            normalized.append((article_id, url, source["domain"], json.dumps(row, ensure_ascii=False)))
        complete = len(rows) < actual_limit or page * actual_limit >= found
        capped = not complete and (page + 1) * actual_limit > 20000
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO articles(article_id,canonical_url,domain,record) VALUES(?,?,?,?)", normalized)
            self.db.execute("UPDATE sources SET next_page=?,complete=?,found=?,capped=? WHERE domain=?",
                            (page + 1, complete, found, capped, source["domain"]))
            self.db.execute("UPDATE requests SET status='success',raw_path=? WHERE id=?", (str(path), request_id))

    def articles(self):
        results = []
        for row in self.db.execute("SELECT * FROM articles ORDER BY article_id"):
            result = dict(row)
            result.update(json.loads(result.pop("record")))
            result["relevance_status"] = "needs_review"
            results.append(result)
        return results

    def save_extraction(self, article_id, status, text="", method="", note=""):
        with self.db:
            self.db.execute("""UPDATE articles SET extraction_status=?,opening_text=?,extraction_method=?,
                extraction_note=?,extracted_at=? WHERE article_id=?""",
                (status, text, method, note, utc_now(), article_id))

    def coverage(self):
        result = []
        for row in self.db.execute("SELECT * FROM sources ORDER BY position"):
            source = json.loads(row["metadata"])
            count = self.db.execute("SELECT count(*) FROM articles WHERE domain=?", (row["domain"],)).fetchone()[0]
            extracted = self.db.execute("SELECT count(*) FROM articles WHERE domain=? AND extraction_status='extracted'", (row["domain"],)).fetchone()[0]
            requests = self.db.execute("SELECT count(*) FROM requests WHERE domain=?", (row["domain"],)).fetchone()[0]
            result.append(dict(source, articles=count, extracted=extracted, requests=requests,
                               next_page=row["next_page"], complete=bool(row["complete"]), found=row["found"], capped=bool(row["capped"])))
        return result
