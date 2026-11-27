import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, THE_NEWS_API_TOKEN="")
        return subprocess.run([sys.executable, "-m", "carneynews", *args], cwd=ROOT,
                              env=env, capture_output=True, text=True)

    def test_plan_shows_both_perspectives_without_creating_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "untouched"
            result = self.run_cli("--data", str(data), "plan")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mark Carney", result.stdout)
            self.assertIn("left", result.stdout)
            self.assertIn("right", result.stdout)
            self.assertFalse(data.exists())

    def test_collect_without_token_has_actionable_error_and_no_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "untouched"
            result = self.run_cli("--data", str(data), "collect", "--max-requests", "1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("THE_NEWS_API_TOKEN", result.stderr)
            self.assertFalse(data.exists())


if __name__ == "__main__":
    unittest.main()
