import csv
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit


def fixture(domain, number, **overrides):
    row = {
        "uuid": f"{domain}-{number}", "title": f"Mark Carney story {number}",
        "description": "A description", "keywords": "Carney", "snippet": "Short snippet",
        "url": f"https://{domain}/news/{number}", "image_url": "",
        "language": "en", "published_at": "2026-11-10T12:00:00Z",
        "source": domain, "categories": ["politics"], "relevance_score": 4.0,
    }
    return dict(row, **overrides)


def response(rows, found=None, limit=3):
    return {"meta": {"found": len(rows) if found is None else found,
                     "returned": len(rows), "limit": limit, "page": 1}, "data": rows}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        try:
            self.config_mod = importlib.import_module("carneynews.config")
            self.store_mod = importlib.import_module("carneynews.store")
            self.collect_mod = importlib.import_module("carneynews.collect")
            self.export_mod = importlib.import_module("carneynews.export")
        except ModuleNotFoundError:
            self.fail("The collection pipeline has not been implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {
            "query": '"Mark Carney" | "Carney government"', "language": "en",
            "start": "2026-10-01", "end": "2026-11-24", "page_size": 3,
            "sources": [
                {"domain": "cbc.ca", "name": "CBC", "country": "ca", "group": "left",
                 "rating": "Lean Left", "rating_url": "https://example.org/cbc", "confidence": "low"},
                {"domain": "nationalpost.com", "name": "National Post", "country": "ca", "group": "right",
                 "rating": "Lean Right", "rating_url": "https://example.org/np", "confidence": "low"},
            ],
        }

    def store(self):
        store = self.store_mod.Store(self.root / "data", self.config)
        self.addCleanup(store.close)
        return store

    def test_configuration_rejects_reversed_dates_and_missing_perspective(self):
        self.config_mod.validate(self.config)
        with self.assertRaises(ValueError):
            self.config_mod.validate(dict(self.config, start="2026-12-01"))
        with self.assertRaises(ValueError):
            self.config_mod.validate(dict(self.config, sources=self.config["sources"][:1]))

    def test_expanded_sampling_plan_requires_a_reserve_and_both_perspectives(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config/north-america.json").read_text())
        self.config_mod.validate(config)
        self.assertEqual((config["start"], config["end"]), ("2025-03-14", "2026-11-25"))
        self.assertEqual(config["sampling"]["target_outlets"], 20)
        self.assertEqual(config["sampling"]["articles_per_outlet"], 25)
        self.assertGreater(config["sampling"]["candidate_pool_per_outlet"], 25)
        self.assertEqual(len(config["sources"]), config["sampling"]["target_outlets"])
        self.assertEqual(
            {country: sum(source["country"] == country for source in config["sources"])
             for country in ("ca", "us")},
            {"ca": 10, "us": 10},
        )
        domains = {source["domain"] for source in config["sources"]}
        self.assertIn("washingtontimes.com", domains)
        self.assertIn("washingtonpost.com", domains)
        self.assertNotIn("ctvnews.ca", domains)
        self.assertIn("left", config["sampling"]["minimum_groups"])
        self.assertIn("right", config["sampling"]["minimum_groups"])

        invalid = dict(config, sampling=dict(config["sampling"], candidate_pool_per_outlet=24))
        with self.assertRaises(ValueError):
            self.config_mod.validate(invalid)
        invalid = dict(config, sources=config["sources"][:-1])
        with self.assertRaises(ValueError):
            self.config_mod.validate(invalid)
        invalid = dict(config, sampling=dict(config["sampling"], shortfall_redistribution="us_then_canada"))
        with self.assertRaises(ValueError):
            self.config_mod.validate(invalid)

    def test_request_uses_fixed_window_domain_and_encoded_phrase_without_unsupported_locale(self):
        from carneynews.api import build_url
        parts = urlsplit(build_url(self.config, self.config["sources"][0], 2, "secret+key"))
        query = parse_qs(parts.query)
        self.assertEqual(query["search"], ['"Mark Carney" | "Carney government"'])
        self.assertEqual(query["domains"], ["cbc.ca"])
        self.assertEqual(query["published_before"], ["2026-11-25T00:00:00"])
        self.assertEqual(query["page"], ["2"])
        self.assertEqual(query["api_token"], ["secret+key"])
        self.assertNotIn("locale", query)

    def test_round_robin_resume_and_successful_raw_snapshots(self):
        store = self.store()
        calls = []
        def request(source, page):
            calls.append((source["domain"], page))
            return response([fixture(source["domain"], page * 3 + i) for i in range(3)], found=6)
        self.collect_mod.collect(store, self.config, request, max_requests=2, daily_limit=90, day="2026-11-25")
        self.assertEqual(calls, [("cbc.ca", 1), ("nationalpost.com", 1)])
        self.collect_mod.collect(store, self.config, request, max_requests=2, daily_limit=90, day="2026-11-25")
        self.assertEqual(calls[2:], [("cbc.ca", 2), ("nationalpost.com", 2)])
        self.assertEqual(len(store.articles()), 12)
        self.assertEqual(len(list((self.root / "data/raw").glob("*.json"))), 4)
        self.assertTrue(all(row["complete"] for row in store.coverage()))

    def test_local_daily_quota_survives_rerun(self):
        store = self.store()
        def request(source, page):
            return response([fixture(source["domain"], page * 3 + i) for i in range(3)], found=100)
        self.collect_mod.collect(store, self.config, request, max_requests=90, daily_limit=2, day="2026-11-25")
        result = self.collect_mod.collect(store, self.config, request, max_requests=90, daily_limit=2, day="2026-11-25")
        self.assertEqual(result["requests"], 0)
        self.assertEqual(len(store.articles()), 6)
        result = self.collect_mod.collect(store, self.config, request, max_requests=1, daily_limit=2, day="2026-11-26")
        self.assertEqual(result["requests"], 1)

    def test_failure_does_not_advance_page_and_counts_attempt(self):
        store = self.store()
        from carneynews.api import APIError
        def request(source, page):
            raise APIError("quota", status=402)
        with self.assertRaises(APIError):
            self.collect_mod.collect(store, self.config, request, max_requests=2, daily_limit=90, day="2026-11-25")
        self.assertEqual(store.coverage()[0]["next_page"], 1)
        self.assertEqual(store.requests_today("2026-11-25"), 1)
        self.assertEqual(store.articles(), [])

    def test_tracking_url_dedup_preserves_identity_and_flags_relevance_for_review(self):
        store = self.store()
        rows = [fixture("cbc.ca", 1), fixture("cbc.ca", 2, url="https://www.cbc.ca/news/1?utm_source=x#top")]
        self.collect_mod.collect(store, self.config, lambda s, p: response(rows) if s["domain"] == "cbc.ca" else response([]),
                                 max_requests=2, daily_limit=90, day="2026-11-25")
        self.assertEqual(len(store.articles()), 1)
        self.assertEqual(store.articles()[0]["relevance_status"], "needs_review")

    def test_unexpected_source_is_rejected_without_advancing(self):
        store = self.store()
        with self.assertRaises(ValueError):
            self.collect_mod.collect(store, self.config, lambda s, p: response([fixture("evil.example", 1)]),
                                     max_requests=1, daily_limit=90, day="2026-11-25")
        self.assertEqual(store.coverage()[0]["next_page"], 1)

    def test_out_of_window_or_wrong_language_response_does_not_enter_dataset(self):
        store = self.store()
        for overrides in ({"published_at": "2025-01-01T12:00:00Z"}, {"language": "fr"}):
            with self.assertRaises(ValueError):
                self.collect_mod.collect(store, self.config,
                    lambda s, p: response([fixture(s["domain"], 1, **overrides)]),
                    max_requests=1, daily_limit=90, day="2026-11-25")
        self.assertEqual(store.articles(), [])

    def test_unexpected_transport_failure_never_persists_credential_url(self):
        store = self.store()
        def request(source, page):
            raise OSError("https://api.example/?api_token=SECRET_SHOULD_NOT_BE_SAVED")
        with self.assertRaises(OSError):
            self.collect_mod.collect(store, self.config, request, max_requests=1, daily_limit=90, day="2026-11-25")
        error = store.db.execute("SELECT error FROM requests").fetchone()[0]
        self.assertNotIn("SECRET", error)

    def test_server_actual_limit_drives_pagination(self):
        store = self.store()
        self.collect_mod.collect(store, self.config, lambda s, p: response([fixture(s["domain"], 1)], found=10, limit=1),
                                 max_requests=1, daily_limit=90, day="2026-11-25")
        self.assertFalse(store.coverage()[0]["complete"])

    def test_changed_study_cannot_silently_reuse_checkpoint(self):
        self.store().close()
        with self.assertRaises(ValueError):
            self.store_mod.Store(self.root / "data", dict(self.config, query="PSPP"))

    def test_annotation_export_is_blank_blind_safe_and_never_overwrites(self):
        store = self.store()
        self.collect_mod.collect(store, self.config, lambda s, p: response([fixture(s["domain"], 1, title="=HYPERLINK(\"bad\")")]),
                                 max_requests=1, daily_limit=90, day="2026-11-25")
        article = store.articles()[0]
        store.save_extraction(article["article_id"], "extracted", "Mark Carney announced a new policy. " * 20, "article_html")
        dest = self.root / "export"
        self.export_mod.export(store, dest)
        with (dest / "annotation.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["topic"], "")
        self.assertEqual(rows[0]["sentiment"], "")
        self.assertEqual(rows[0]["status"], "not_started")
        self.assertNotIn("group", rows[0])
        self.assertTrue(rows[0]["headline"].startswith("'="))
        with self.assertRaises(FileExistsError):
            self.export_mod.export(store, dest)

    def test_snippet_only_records_are_not_exported_for_annotation(self):
        store = self.store()
        self.collect_mod.collect(store, self.config, lambda s, p: response([fixture(s["domain"], 1)]),
                                 max_requests=1, daily_limit=90, day="2026-11-25")
        dest = self.root / "export"
        self.export_mod.export(store, dest)
        with (dest / "annotation.csv").open(encoding="utf-8-sig", newline="") as f:
            self.assertEqual(list(csv.DictReader(f)), [])
        with (dest / "coverage.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["articles"], "0")

    def test_export_separates_absent_subject_from_topic_annotation_without_losing_record(self):
        store = self.store()
        self.collect_mod.collect(store, self.config, lambda s, p: response([fixture(s["domain"], 1, title="Hockey federation website hacked")]),
                                 max_requests=1, daily_limit=90, day="2026-11-25")
        store.save_extraction(store.articles()[0]["article_id"], "extracted", "A hockey tournament was disrupted. " * 12, "article_html")
        dest = self.root / "screened"
        self.export_mod.export(store, dest)
        with (dest / "annotation.csv").open(encoding="utf-8-sig", newline="") as f:
            self.assertEqual(list(csv.DictReader(f)), [])
        with (dest / "screening.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["screening_hint"], "no_subject_in_excerpt")
        self.assertEqual(rows[0]["eligibility"], "")

    def test_unrated_sources_can_be_added_without_fabricating_center_rating(self):
        extra = dict(self.config["sources"][0], domain="ctvnews.ca", group="unrated", rating="Not assessed", confidence="not assessed")
        config = dict(self.config, sources=self.config["sources"] + [extra])
        self.config_mod.validate(config)
        store = self.store_mod.Store(self.root / "unrated", config)
        self.addCleanup(store.close)
        self.assertEqual(store.coverage()[-1]["group"], "unrated")

    def test_known_abc_publisher_alias_is_accepted_but_unrelated_urls_are_not(self):
        source = dict(self.config["sources"][0], domain="abcnews.go.com", name="ABC", country="us")
        config = dict(self.config, sources=[source, self.config["sources"][1]])
        store = self.store_mod.Store(self.root / "abc", config)
        self.addCleanup(store.close)
        self.collect_mod.collect(store, config, lambda s, p: response([fixture("abcnews.go.com", 1, url="https://abcnews.com/story/1")]),
                                 max_requests=1, daily_limit=90, day="2026-11-25")
        self.assertEqual(len(store.articles()), 1)
        self.assertFalse(self.store_mod.matches_publisher("https://abcnews.com.evil.example/story", "abcnews.go.com"))

    def test_targeted_collection_retains_full_frame_but_only_requests_selected_source(self):
        store = self.store()
        self.collect_mod.collect(store, self.config, lambda s, p: response([fixture(s["domain"], 1)]),
            max_requests=2, daily_limit=90, day="2026-11-25", domains=["cbc.ca"])
        self.assertEqual(store.coverage()[0]["articles"], 1)
        self.assertEqual(store.coverage()[1]["requests"], 0)


if __name__ == "__main__":
    unittest.main()
