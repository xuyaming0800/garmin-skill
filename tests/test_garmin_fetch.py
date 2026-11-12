import importlib.util
import unittest
from datetime import date
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / ".agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py"
)
SPEC = importlib.util.spec_from_file_location("garmin_fetch", SCRIPT)
garmin_fetch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(garmin_fetch)


class DateWindowTests(unittest.TestCase):
    def test_inclusive_window(self):
        self.assertEqual(
            garmin_fetch.date_window(7, date(2026, 11, 13)),
            (date(2026, 11, 7), date(2026, 11, 13)),
        )

    def test_rejects_oversized_window(self):
        with self.assertRaises(ValueError):
            garmin_fetch.date_window(91, date(2026, 11, 13))


class RedactionTests(unittest.TestCase):
    def test_removes_secrets_identity_and_location_recursively(self):
        raw = {
            "accessToken": "secret",
            "displayName": "athlete",
            "activity": {
                "startLatitude": 31.2,
                "longitude": 121.4,
                "distance": 5000,
            },
        }
        self.assertEqual(
            garmin_fetch.redact(raw),
            {"activity": {"distance": 5000}},
        )

    def test_location_can_be_explicitly_retained(self):
        self.assertEqual(
            garmin_fetch.redact({"startLatitude": 31.2}, include_location=True),
            {"startLatitude": 31.2},
        )

    def test_exception_text_redacts_email_and_bearer_token(self):
        error = RuntimeError("user@example.com Bearer abc.def.ghi")
        result = garmin_fetch.safe_exception(error)
        self.assertNotIn("user@example.com", result)
        self.assertNotIn("abc.def.ghi", result)


if __name__ == "__main__":
    unittest.main()
