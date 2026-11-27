"""Small quota-accounted probes: domain indexing versus query matching."""
import json
from .api import utc_day, utc_now


def diagnose(store, config, request, domains=None, max_requests=8, daily_limit=90, day=None, on_result=None):
    if max_requests < 1 or daily_limit < 1:
        raise ValueError("Request budgets must be positive")
    selected = [s for s in config["sources"] if domains is None or s["domain"] in domains]
    if not selected or (domains and set(domains) - {s["domain"] for s in selected}):
        raise ValueError("Diagnostic domains must be in the selected study config")
    results, used = [], 0
    directory = store.directory / "diagnostics"
    directory.mkdir(exist_ok=True)
    for source in selected:
        result = {"domain": source["domain"], "group": source["group"]}
        probes = [
            ("study_matches", config, source),
            ("broad_name_matches", dict(config, query="Carney", search_fields="title,description,main_text"), source),
            ("domain_articles", dict(config, query=""), source),
            ("www_domain_articles", dict(config, query=""), dict(source, domain="www." + source["domain"])),
        ]
        for label, probe_config, probe_source in probes:
            if used >= max_requests:
                break
            request_id = store.reserve_request(source["domain"], 0, day or utc_day(), daily_limit)
            if request_id is None:
                break
            used += 1
            try:
                payload = request(probe_config, probe_source)
                result[label] = payload["meta"]["found"]
                path = directory / f"{request_id:06d}-{source['domain']}-{label}.json"
                with path.open("x", encoding="utf-8") as f:
                    json.dump({"checked_at": utc_now(), "domain": probe_source["domain"],
                               "query": probe_config["query"], "probe": label, "response": payload}, f, indent=2)
                with store.db:
                    store.db.execute("UPDATE requests SET status='diagnostic',raw_path=? WHERE id=?", (str(path), request_id))
            except Exception:
                store.fail_request(request_id, "Diagnostic failed; credentials omitted")
                raise
            if on_result:
                on_result(source["domain"], label, result[label])
        if len(result) > 2:
            results.append(result)
        if used >= max_requests:
            break
    return results
