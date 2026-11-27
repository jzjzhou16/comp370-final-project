"""Study protocol validation; never store credentials in a study config."""
from datetime import date, timedelta
import json
from pathlib import Path
import re


def validate(config):
    start, end = date.fromisoformat(config["start"]), date.fromisoformat(config["end"])
    if start > end:
        raise ValueError("start must be on or before end")
    if not isinstance(config["query"], str) or not config["query"].strip():
        raise ValueError("query must be nonempty")
    if not isinstance(config["page_size"], int) or not 1 <= config["page_size"] <= 100:
        raise ValueError("page_size must be between 1 and 100; free accounts support 3")
    sources = config["sources"]
    if not {"left", "right"} <= {s["group"] for s in sources}:
        raise ValueError("Select at least one left and one right source")
    domains = [s["domain"] for s in sources]
    if len(set(domains)) != len(domains):
        raise ValueError("Source domains must be unique")
    for source in sources:
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", source["domain"]):
            raise ValueError("Use bare lowercase publisher domains")
        if source["country"] not in {"ca", "us", "mx"}:
            raise ValueError("Sources must be North American publishers")
        if source["group"] not in {"left", "center", "right", "unrated"}:
            raise ValueError("Unknown source group")
        for key in ("name", "rating", "rating_url", "confidence"):
            if not source.get(key):
                raise ValueError(f"Source missing {key}")
    if "api_token" in config or "api_key" in config:
        raise ValueError("Keep API keys out of config; use THE_NEWS_API_TOKEN")
    if config.get("search_fields", "title,main_text") not in {"title,main_text", "title,description", "title,description,main_text"}:
        raise ValueError("Unsupported study search_fields")
    sampling = config.get("sampling")
    if sampling is not None:
        if not isinstance(sampling, dict):
            raise ValueError("sampling must be an object")
        for key in ("target_outlets", "articles_per_outlet", "candidate_pool_per_outlet", "seed"):
            if not isinstance(sampling.get(key), int) or sampling[key] < 1:
                raise ValueError(f"sampling.{key} must be a positive integer")
        if sampling["candidate_pool_per_outlet"] < sampling["articles_per_outlet"]:
            raise ValueError("candidate_pool_per_outlet must be at least articles_per_outlet")
        if sampling.get("selection") != "random_after_human_screening":
            raise ValueError("Unsupported sampling selection method")
        if sampling.get("shortfall_redistribution") != "canada_then_us":
            raise ValueError("Unsupported sampling shortfall redistribution")
        if sampling.get("outlet_selection") != "availability_balanced":
            raise ValueError("Unsupported sampling outlet selection method")
        if sampling.get("fallback") != "most_recent_25_when_common_window_coverage_is_insufficient":
            raise ValueError("Unsupported sampling fallback")
        countries = sampling.get("countries")
        if not isinstance(countries, list) or not countries or not set(countries) <= {"ca", "us"}:
            raise ValueError("sampling.countries must select Canada and/or the US")
        if len(sources) != sampling["target_outlets"]:
            raise ValueError("The selected source count must match sampling.target_outlets")
        if any(source["country"] not in countries for source in sources):
            raise ValueError("Every selected source must belong to a sampling country")
        minimum_groups = sampling.get("minimum_groups")
        if not isinstance(minimum_groups, list) or not {"left", "right"} <= set(minimum_groups):
            raise ValueError("sampling.minimum_groups must include left and right")
        if sampling["target_outlets"] * sampling["articles_per_outlet"] != 500:
            raise ValueError("Sampling quotas must total 500 usable articles")
    return config


def load(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def boundaries(config):
    return (config["start"] + "T00:00:00",
            (date.fromisoformat(config["end"]) + timedelta(days=1)).isoformat() + "T00:00:00")
