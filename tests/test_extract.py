import importlib
import unittest


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module("carneynews.extract")
        except ModuleNotFoundError:
            self.fail("Publisher extraction has not been implemented")

    def test_article_markup_excludes_navigation_asides_and_script_text(self):
        html = """<nav><p>Ignore me</p></nav><article><p>Mark Carney announced a policy.</p>
        <aside><p>Related: a different story.</p></aside>
        <script>garbage()</script><p>The policy was announced today.</p></article>"""
        text, method = self.module.parse_opening(html)
        self.assertEqual(text, "Mark Carney announced a policy. The policy was announced today.")
        self.assertEqual(method, "article_html")

    def test_structured_article_body_is_limited_to_150_words(self):
        import json
        body = " ".join(f"word{i}" for i in range(200))
        html = '<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "NewsArticle", "articleBody": body,
            "isAccessibleForFree": True}) + "</script>"
        text, method = self.module.parse_opening(html)
        self.assertEqual(len(text.split()), 150)
        self.assertEqual(text.split()[-1], "word149")
        self.assertEqual(method, "jsonld_article_body")

    def test_explicit_paywall_is_not_extracted_from_hidden_structured_data(self):
        html = '<script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":false,"articleBody":"Hidden article"}</script><article><p>Subscribe</p></article>'
        with self.assertRaises(self.module.ExtractionError):
            self.module.parse_opening(html)

    def test_related_story_text_is_removed_from_structured_body_before_truncation(self):
        import json
        related = "CARNEY CASTS HIMSELF AS NATO DEFENDER"
        body = "Hillary Clinton discussed Mark Carney. " + related + " The interview continued with questions about alliances."
        html = '<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle", "articleBody": body}) + '</script>'
        html += '<article><p>Hillary Clinton discussed Mark Carney.</p><p><a href="/other-story"><strong>' + related + '</strong></a></p><p>The interview continued with questions about alliances.</p></article>'
        text, _ = self.module.parse_opening(html)
        self.assertNotIn(related, text)
        self.assertIn("The interview continued", text)

    def test_inline_citations_and_uppercase_quotations_are_preserved(self):
        html = '<article><p>Mark Carney told <a href="/source">the newspaper</a> that "WE WILL ACT" today.</p></article>'
        text, _ = self.module.parse_opening(html)
        self.assertIn("the newspaper", text)
        self.assertIn('"WE WILL ACT"', text)

    def test_historical_pilot_can_be_reprocessed_without_network(self):
        import test_pipeline as pipeline
        from unittest.mock import patch
        helper = pipeline.PipelineTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        store = helper.store()
        helper.collect_mod.collect(store, helper.config,
            lambda s, p: pipeline.response([pipeline.fixture(s["domain"], 1)]),
            max_requests=1, daily_limit=90, day="2026-11-25")
        article = store.articles()[0]
        pages = store.directory / "pages"
        pages.mkdir()
        text = "Mark Carney announced housing measures. " * 10
        (pages / f"{article['article_id']}-1.html").write_text("<article><p>" + text + "</p></article>")
        with patch("carneynews.extract.read_public_page", side_effect=AssertionError("Offline reprocessing must not fetch")):
            self.assertEqual(self.module.reextract_saved(store), 1)
        saved = store.articles()[0]
        self.assertEqual(saved["extraction_status"], "extracted")
        self.assertEqual(saved["opening_text"], text.strip())

    def test_generic_page_paragraphs_and_meta_description_are_not_an_opening(self):
        html = '<meta name="description" content="Mark Carney"><p>Subscribe now.</p>'
        with self.assertRaises(self.module.ExtractionError):
            self.module.parse_opening(html)

    def test_robot_disallow_prevents_article_request(self):
        calls = []
        def read(url, domain):
            calls.append(url)
            if url.endswith("robots.txt"):
                return "User-agent: *\nDisallow: /news/"
            self.fail("Disallowed article must never be fetched")
        fetcher = self.module.PublisherFetcher(read=read, delay=0)
        with self.assertRaises(self.module.ExtractionError):
            fetcher.fetch("https://cbc.ca/news/1", "cbc.ca")
        self.assertEqual(len(calls), 1)

    def test_robot_failure_fails_closed(self):
        def read(url, domain):
            raise OSError("offline")
        with self.assertRaises(self.module.ExtractionError):
            self.module.PublisherFetcher(read=read, delay=0).fetch("https://cbc.ca/news/1", "cbc.ca")

    def test_allowed_fetch_caches_robots_and_extracts_article(self):
        calls = []
        def read(url, domain):
            calls.append(url)
            return "User-agent: *\nAllow: /" if url.endswith("robots.txt") else "<article><p>Mark Carney announced a policy today.</p></article>"
        fetcher = self.module.PublisherFetcher(read=read, delay=0)
        self.assertEqual(fetcher.fetch("https://cbc.ca/news/1", "cbc.ca")[0], "Mark Carney announced a policy today.")
        fetcher.fetch("https://cbc.ca/news/2", "cbc.ca")
        self.assertEqual(sum(x.endswith("robots.txt") for x in calls), 1)

    def test_fetch_rejects_off_source_urls_before_any_network(self):
        def read(url, domain):
            self.fail("Unexpected source must not be fetched")
        with self.assertRaises(self.module.ExtractionError):
            self.module.PublisherFetcher(read=read, delay=0).fetch("http://localhost/news", "cbc.ca")


if __name__ == "__main__":
    unittest.main()
