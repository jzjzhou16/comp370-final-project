"""Round-robin collection: no global early stop that could hide one perspective."""
import json

from .api import APIError, utc_day


def collect(store, config, request, max_requests=90, daily_limit=90, day=None, on_page=None, domains=None):
    if max_requests < 1 or daily_limit < 1:
        raise ValueError("Request budgets must be positive")
    if domains is not None and (not domains or set(domains) - {s["domain"] for s in config["sources"]}):
        raise ValueError("Collection domains must be in the selected study config")
    used = 0
    while used < max_requests:
        source_state = store.next_source(domains)
        if source_state is None:
            break
        source = json.loads(source_state["metadata"])
        page = source_state["next_page"]
        request_id = store.reserve_request(source["domain"], page, day or utc_day(), daily_limit)
        if request_id is None:
            break
        used += 1
        try:
            payload = request(source, page)
            store.save_page(request_id, source, page, payload)
        except Exception as exc:
            # Never persist exception strings from arbitrary transports: URLs may contain keys.
            store.fail_request(request_id, "API error" if isinstance(exc, APIError) else type(exc).__name__)
            raise
        if on_page:
            on_page(source, page, len(payload["data"]))
    return {"requests": used, "articles": len(store.articles())}
