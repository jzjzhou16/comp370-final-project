"""Conservative publisher extraction with robots checks and explicit failures."""
from html import unescape
from html.parser import HTMLParser
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .store import canonical_url, matches_publisher

USER_AGENT = "COMP370Research/1.0"


class ExtractionError(RuntimeError):
    pass


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.paragraphs = []
        self.current = []
        self.scripts = []
        self.script = None
        self.link_text = []
        self.in_link = False
        self.links = []
        self.related = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self.script = []
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)
        if tag == "p":
            self.current = []
            self.links = []
        if tag == "a" and "p" in self.stack:
            self.in_link = True
            self.link_text = []

    def handle_data(self, data):
        if self.script is not None and self.stack and self.stack[-1] == "script":
            self.script.append(data)
        if "article" in self.stack and "p" in self.stack and not set(self.stack) & {"aside", "nav", "figure", "figcaption", "script", "style", "header", "footer"}:
            self.current.append(data)
        if self.in_link:
            self.link_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_link:
            self.links.append("".join(self.link_text))
            self.in_link = False
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag == "p" and self.current:
            paragraph = " ".join("".join(self.current).split())
            linked = " ".join(" ".join(self.links).split())
            # Standalone link-only paragraphs are recommendations, not inline citations.
            if linked and paragraph == linked and len(paragraph.split()) >= 4:
                self.related.append(paragraph)
            else:
                self.paragraphs.append(paragraph)
            self.current = []
        if tag in self.stack:
            reverse_index = self.stack[::-1].index(tag)
            del self.stack[len(self.stack) - reverse_index - 1:]


def article_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from article_objects(item)
    elif isinstance(value, dict):
        kind = value.get("@type", [])
        kinds = [kind] if isinstance(kind, str) else kind
        if isinstance(kinds, list) and any(str(k).rsplit("/", 1)[-1] in {"Article", "NewsArticle", "ReportageNewsArticle"} for k in kinds):
            yield value
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in value:
                yield from article_objects(value[key])


def parse_opening(html):
    parser = ArticleParser()
    parser.feed(html)
    objects = []
    for script in parser.scripts:
        try:
            objects.extend(article_objects(json.loads(script)))
        except (ValueError, TypeError):
            continue
    if any(str(obj.get("isAccessibleForFree", "true")).lower() in {"false", "0"} for obj in objects):
        raise ExtractionError("Publisher marks the article as requiring paid access; use an authorized archive.")
    for obj in objects:
        if isinstance(obj.get("articleBody"), str) and obj["articleBody"].strip():
            body = obj["articleBody"]
            # Remove inline markup from structured article bodies.
            plain = HTMLParserText()
            plain.feed(unescape(body))
            text = " ".join("".join(plain.chunks).split())
            for related in parser.related:
                text = text.replace(related, " ")
            return " ".join(text.split()[:150]), "jsonld_article_body"
    if parser.paragraphs:
        return " ".join(" ".join(parser.paragraphs).split()[:150]), "article_html"
    raise ExtractionError("No article body or article paragraphs found; manual extraction needed.")


class HTMLParserText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []

    def handle_data(self, data):
        self.chunks.append(data)

    def handle_starttag(self, tag, _attrs):
        if tag in {"p", "br", "div"}:
            self.chunks.append(" ")

    def handle_endtag(self, tag):
        if tag in {"p", "div"}:
            self.chunks.append(" ")


def read_public_page(url, domain):
    class ScopedRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not matches_publisher(newurl, domain) or urlsplit(newurl).scheme not in {"https", "http"}:
                raise ExtractionError("Redirect leaves the selected publisher; skipped.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
    with build_opener(ScopedRedirect()).open(request, timeout=30) as response:
        if response.headers.get_content_type() not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ExtractionError("Publisher response is not text or HTML.")
        data = response.read(3_000_001)
        if len(data) > 3_000_000:
            raise ExtractionError("Publisher page exceeds the 3 MB limit.")
        return data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


class PublisherFetcher:
    def __init__(self, read=read_public_page, delay=2.0):
        self.read = read
        self.delay = delay
        self.robots = {}
        self.last = {}
        self.last_html = ""

    def fetch(self, url, domain):
        self.last_html = ""
        try:
            canonical_url(url)
        except ValueError:
            raise ExtractionError("Invalid publisher URL") from None
        if not matches_publisher(url, domain):
            raise ExtractionError("Article URL is outside the selected publisher")
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        if origin not in self.robots:
            rules = RobotFileParser(origin + "/robots.txt")
            try:
                rules.parse(self.read(origin + "/robots.txt", domain).splitlines())
            except HTTPError as exc:
                if exc.code in {404, 410}:
                    rules.parse(["User-agent: *", "Allow: /"])
                else:
                    raise ExtractionError("Cannot verify publisher robots rules; skipped.") from None
            except (OSError, ExtractionError):
                raise ExtractionError("Cannot verify publisher robots rules; skipped.") from None
            self.robots[origin] = rules
        rules = self.robots[origin]
        if not rules.can_fetch(USER_AGENT, url):
            raise ExtractionError("Publisher robots rules disallow this URL.")
        delay = max(self.delay, rules.crawl_delay(USER_AGENT) or 0)
        if delay > 60:
            raise ExtractionError("Publisher requests a crawl delay over 60 seconds; use manual access.")
        wait = max(0, self.last.get(domain, 0) + delay - time.monotonic())
        if wait:
            time.sleep(wait)
        try:
            self.last_html = self.read(url, domain)
        except (OSError, ExtractionError):
            raise ExtractionError("Publisher access failed; may be blocked, unavailable, or require login.") from None
        finally:
            self.last[domain] = time.monotonic()
        return parse_opening(self.last_html)


def fetch_openings(store, limit=20, retry_failed=False, on_article=None):
    if limit < 1:
        raise ValueError("Fetch limit must be positive")
    fetcher = PublisherFetcher()
    processed = 0
    candidates = [a for a in store.articles() if a["extraction_status"] == "pending" or
                  (retry_failed and a["extraction_status"] != "extracted")]
    # Interleave outlets so a small pilot measures extraction failures across perspectives.
    groups = {}
    for article in candidates:
        groups.setdefault(article["domain"], []).append(article)
    queue = []
    while any(groups.values()):
        for domain in groups:
            if groups[domain]:
                queue.append(groups[domain].pop(0))
    for article in queue[:limit]:
        try:
            opening, method = fetcher.fetch(article["url"], article["domain"])
            if len(opening.split()) < 20:
                raise ExtractionError("Extracted text is too short; manual review required.")
            store.save_extraction(article["article_id"], "extracted", opening, method,
                                  "First 150 words; human text verification still required.")
        except ExtractionError as exc:
            store.save_extraction(article["article_id"], "needs_manual", note=str(exc))
        finally:
            if fetcher.last_html:
                directory = store.directory / "pages"
                directory.mkdir(exist_ok=True)
                stamp = time.time_ns()
                (directory / f"{article['article_id']}-{stamp}.html").write_text(fetcher.last_html, encoding="utf-8")
        processed += 1
        if on_article:
            on_article(article["article_id"])
    return processed


def reextract_saved(store):
    """Reprocess archived pages without network access or modifying previous exports."""
    processed = 0
    for article in store.articles():
        pages = sorted((store.directory / "pages").glob(f"{article['article_id']}-*.html"))
        if not pages:
            continue
        try:
            text, method = parse_opening(pages[-1].read_text(encoding="utf-8"))
            if len(text.split()) < 20:
                raise ExtractionError("Extracted text is too short; manual review required.")
            store.save_extraction(article["article_id"], "extracted", text, method,
                                  "Reprocessed saved HTML; related links removed; verify text manually.")
        except ExtractionError as exc:
            store.save_extraction(article["article_id"], "needs_manual", note=str(exc))
        processed += 1
    return processed
