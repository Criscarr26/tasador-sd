"""Guards the self-contained serverless API (api/index.py) against drift
from the domain source of truth (tasador-core). If the inlined ranges or
prediction ever diverge from the package, CI fails here.

Run from the repo root (CI installs tasador-core with `pip install -e
packages/core_py`):
    python -m unittest discover tests -v
"""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("sl_index", ROOT / "api" / "index.py")
serverless = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serverless)

from tasador_core import schema
from tasador_core.model import predict_from_params


class TestServerlessParity(unittest.TestCase):
    def test_numeric_ranges_match_source(self):
        for field in serverless.NUMERIC_FEATURES:
            self.assertEqual(
                serverless.APPRAISAL_RANGES[field], schema.RANGES[field],
                f"range for {field} drifted from tasador_core",
            )

    def test_feature_order_matches_source(self):
        self.assertEqual(serverless.NUMERIC_FEATURES, schema.NUMERIC_FEATURES)

    def test_sectors_match_the_trained_model(self):
        # The serverless app validates against the exported sectors, which
        # must be exactly the sectors the model knows.
        self.assertEqual(sorted(serverless.MODEL["sectors"]), sorted(schema.KNOWN_SECTORS))

    def test_predictions_match_tasador_core(self):
        for case in serverless.MODEL["reference_cases"]:
            edge = serverless.predict_price(case["input"])
            core = predict_from_params(serverless.MODEL, case["input"])
            self.assertAlmostEqual(edge, core, places=9)
            self.assertAlmostEqual(edge, case["expected"], places=6)


if __name__ == "__main__":
    unittest.main()
