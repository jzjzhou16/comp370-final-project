from email.message import Message
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from carneynews.api import APIError, fetch_page


class APITests(unittest.TestCase):
    def setUp(self):
        self.config = {"start": "2026-10-01", "end": "2026-11-24", "query": '"Mark Carney"',
                       "language": "en", "page_size": 3}

    def test_http_quota_error_preserves_status_without_leaking_token(self):
        url = "https://api.thenewsapi.com/v1/news/all?api_token=secret-example-token"
        with patch("carneynews.api.urlopen", side_effect=HTTPError(url, 402, "quota", Message(), None)):
            with self.assertRaises(APIError) as error:
                fetch_page(self.config, {"domain": "cbc.ca"}, 1, "secret-example-token")
        self.assertEqual(error.exception.status, 402)
        self.assertNotIn("secret-example-token", str(error.exception))

    def test_network_errors_hide_sensitive_transport_details(self):
        with patch("carneynews.api.urlopen", side_effect=URLError("api_token=secret-example-token")):
            with self.assertRaises(APIError) as error:
                fetch_page(self.config, {"domain": "cbc.ca"}, 1, "secret-example-token")
        self.assertNotIn("secret-example-token", str(error.exception))

    def test_rate_limit_exposes_safe_retry_delay_without_token(self):
        headers = Message()
        headers["Retry-After"] = "60"
        with patch("carneynews.api.urlopen", side_effect=HTTPError("https://example.org/?api_token=secret", 429, "rate", headers, None)):
            with self.assertRaises(APIError) as error:
                fetch_page(self.config, {"domain": "cbc.ca"}, 1, "secret")
        self.assertEqual(error.exception.retry_after, 60)
        self.assertIn("60", str(error.exception))


if __name__ == "__main__":
    unittest.main()
