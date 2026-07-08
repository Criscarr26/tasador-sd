"""Contract tests for the API against the real trained model.

Run from apps/api with a venv that has fastapi + httpx + the model stack:
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


class TestHealth(unittest.TestCase):
    def test_health_reports_model_version(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_version"], main.MODEL_VERSION)


class TestAppraisals(unittest.TestCase):
    def test_reference_cases_match_the_pipeline(self):
        """The exported reference predictions ARE the API's answers."""
        for case in main.model_params["reference_cases"]:
            response = client.post("/v1/appraisals", json=case["input"])
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertAlmostEqual(body["estimate"], case["expected"], places=2)
            self.assertEqual(body["model_version"], main.MODEL_VERSION)
            self.assertLess(body["range_low"], body["estimate"])
            self.assertGreater(body["range_high"], body["estimate"])

    def test_unknown_sector_is_rejected(self):
        case = dict(main.model_params["reference_cases"][0]["input"], sector="Gurabo")
        response = client.post("/v1/appraisals", json=case)
        self.assertEqual(response.status_code, 422)
        self.assertTrue(any("unknown sector" in p for p in response.json()["detail"]))

    def test_out_of_range_area_is_rejected(self):
        case = dict(main.model_params["reference_cases"][0]["input"], area_m2=5)
        response = client.post("/v1/appraisals", json=case)
        self.assertEqual(response.status_code, 422)


class TestSecurity(unittest.TestCase):
    def test_security_headers_present(self):
        response = client.get("/health")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertIn("content-security-policy", response.headers)
        self.assertIn("strict-transport-security", response.headers)

    def test_cors_allows_only_the_web_app(self):
        allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(
            allowed.headers.get("access-control-allow-origin"), "http://localhost:3000"
        )
        blocked = client.get("/health", headers={"Origin": "https://evil.example.com"})
        self.assertIsNone(blocked.headers.get("access-control-allow-origin"))

    def test_rate_limit_returns_429_over_the_cap(self):
        original = main.RATE_LIMIT_PER_MINUTE
        main.RATE_LIMIT_PER_MINUTE = 2
        main._hits.clear()
        try:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/health").status_code, 200)
            throttled = client.get("/health")
            self.assertEqual(throttled.status_code, 429)
            self.assertEqual(throttled.headers.get("Retry-After"), "60")
        finally:
            main.RATE_LIMIT_PER_MINUTE = original
            main._hits.clear()


class TestModelParams(unittest.TestCase):
    def test_params_are_versioned_and_complete(self):
        response = client.get("/v1/model/params")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["version"], main.MODEL_VERSION)
        params = body["params"]
        self.assertEqual(len(params["sectors"]), 10)
        self.assertEqual(len(params["coef"]), 16)
        self.assertEqual(len(params["reference_cases"]), 3)


if __name__ == "__main__":
    unittest.main()
