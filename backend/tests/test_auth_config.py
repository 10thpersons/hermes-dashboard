"""Stdlib dummy-environment configuration regressions; no application startup."""
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

CONFIG = Path(__file__).resolve().parents[1] / "config.py"
DUMMY_KEY = "0123456789abcdef" * 4


class AuthConfigurationTests(unittest.TestCase):
    def test_absent_empty_short_whitespace_and_repetitive_keys_fail(self):
        for value in (None, "", "short", " " * 64, "a" * 64,
                      DUMMY_KEY + "\n", "é" * 64):
            env = {} if value is None else {"DASHBOARD_API_KEY": value}
            with self.subTest(kind=type(value).__name__), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError) as caught:
                    runpy.run_path(str(CONFIG))
                if value:
                    self.assertNotIn(value, str(caught.exception))

    def test_explicit_dummy_key_is_preserved_exactly(self):
        with patch.dict(os.environ, {"DASHBOARD_API_KEY": DUMMY_KEY}, clear=True):
            config = runpy.run_path(str(CONFIG))
        self.assertEqual(config["API_KEY"], DUMMY_KEY)
        self.assertNotEqual(config["API_KEY"], "unrelated-dummy-material")


if __name__ == "__main__":
    unittest.main()
