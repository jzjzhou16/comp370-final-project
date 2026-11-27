import importlib
import json
from pathlib import Path
import tempfile
import unittest

import test_pipeline as pipeline


class DiagnosticTests(unittest.TestCase):
    def test_diagnostics_distinguish_no_query_match_from_no_domain_coverage(self):
        try:
            module = importlib.import_module("carneynews.diagnostics")
        except ModuleNotFoundError:
            self.fail("Source diagnostics have not been implemented")
        helper = pipeline.PipelineTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        store = helper.store()
        seen = []
        def request(config, source):
            seen.append((config["query"], source["domain"]))
            return pipeline.response([], found=0) if config["query"] else pipeline.response([pipeline.fixture("cbc.ca", 1)], found=50)
        results = module.diagnose(store, helper.config, request, domains=["cbc.ca"], max_requests=4, day="2026-11-25")
        self.assertEqual(results[0]["study_matches"], 0)
        self.assertEqual(results[0]["domain_articles"], 50)
        self.assertEqual(store.coverage()[0]["next_page"], 1)
        self.assertEqual(store.requests_today("2026-11-25"), 4)
        self.assertEqual(store.articles(), [])
        self.assertTrue(any(domain == "www.cbc.ca" for query, domain in seen))
