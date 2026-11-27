"""TheNewsAPI boundary. Errors deliberately omit credential-bearing URLs."""
from datetime import datetime, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import boundaries

ENDPOINT = "https://api.thenewsapi.com/v1/news/all"


class APIError(RuntimeError):
    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def build_url(config, source, page, token):
    start, end = boundaries(config)
    params = {
        "api_token": token,
        "domains": source["domain"], "language": config["language"],
        "published_after": start, "published_before": end,
        "sort": "published_at", "limit": config["page_size"], "page": page,
    }
    if config["query"]:
        params.update(search=config["query"], search_fields=config.get("search_fields", "title,main_text"))
    return ENDPOINT + "?" + urlencode(params)


def fetch_page(config, source, page, token):
    req = Request(build_url(config, source, page, token), headers={"User-Agent": "COMP370Research/1.0"})
    try:
        with urlopen(req, timeout=40) as result:
            payload = json.load(result)
    except HTTPError as exc:
        retry_after = None
        if exc.code == 429:
            header = exc.headers.get("Retry-After", "60") if exc.headers else "60"
            retry_after = int(header) if str(header).isdigit() else 60
        advice = {401: "Check your API token.", 402: "Daily API quota reached; resume later.",
                  403: "Check account endpoint permissions.", 429: "Rate limited; resume later."}
        delay_note = f" Wait at least {retry_after} seconds before resuming." if retry_after is not None else ""
        raise APIError(f"TheNewsAPI HTTP {exc.code}. {advice.get(exc.code, 'Resume later; progress is saved.')}{delay_note}",
                       exc.code, retry_after) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise APIError("TheNewsAPI network or JSON error; progress saved. Resume later.") from None
    if not isinstance(payload, dict) or payload.get("error"):
        raise APIError("TheNewsAPI returned an error payload; check your account and parameters.")
    return payload


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def utc_day():
    return datetime.now(timezone.utc).date().isoformat()
