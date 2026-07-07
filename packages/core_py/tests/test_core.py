"""Tests for the shared domain contract. Stdlib unittest only, so they
run in any of the project venvs: python -m unittest discover tests -v
(model tests skip themselves if scikit-learn is not installed)."""

import unittest

from tasador_core import schema

try:
    import sklearn  # noqa: F401

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


VALID_LISTING = {
    "sector": "Bella Vista",
    "area_m2": 95,
    "bedrooms": 2,
    "bathrooms": 2,
    "parking_spots": 1,
    "furnished": 0,
    "age_years": 8,
    "price_dop": 38_500,
    "source_url": "https://example.com/listing/1",
}


class TestSchema(unittest.TestCase):
    def test_valid_listing_passes(self):
        self.assertEqual(schema.validate_listing(VALID_LISTING), [])

    def test_unknown_sector_rejected(self):
        record = {**VALID_LISTING, "sector": "Gurabo"}
        problems = schema.validate_listing(record)
        self.assertTrue(any("unknown sector" in p for p in problems))

    def test_out_of_range_rejected(self):
        record = {**VALID_LISTING, "area_m2": 5, "price_dop": 2_000_000}
        problems = schema.validate_listing(record)
        self.assertEqual(len(problems), 2)

    def test_booleans_are_not_numbers(self):
        record = {**VALID_LISTING, "furnished": True}
        problems = schema.validate_listing(record)
        self.assertTrue(any("furnished" in p for p in problems))

    def test_appraisal_input_ignores_price_and_url(self):
        features = {k: VALID_LISTING[k] for k in schema.FEATURES}
        self.assertEqual(schema.validate_appraisal_input(features), [])

    def test_normalize_sector_variants(self):
        self.assertEqual(schema.normalize_sector("ensanche naco"), "Naco")
        self.assertEqual(schema.normalize_sector("SERRALLES"), "Serrallés")
        self.assertEqual(schema.normalize_sector("piantini "), "Piantini")
        self.assertIsNone(schema.normalize_sector("Gurabo"))

    def test_columns_are_features_plus_price_and_url(self):
        self.assertEqual(schema.COLUMNS[:7], schema.FEATURES)
        self.assertIn(schema.TARGET, schema.COLUMNS)
        self.assertIn("source_url", schema.COLUMNS)


@unittest.skipUnless(HAS_SKLEARN, "scikit-learn not installed in this venv")
class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        import pandas as pd

        from tasador_core import model

        rng = np.random.default_rng(42)
        n = 120
        frame = pd.DataFrame(
            {
                "sector": rng.choice(schema.KNOWN_SECTORS, n),
                "area_m2": rng.integers(40, 300, n),
                "bedrooms": rng.integers(1, 4, n),
                "bathrooms": rng.integers(1, 3, n),
                "parking_spots": rng.integers(0, 3, n),
                "furnished": rng.integers(0, 2, n),
                "age_years": rng.integers(0, 40, n),
            }
        )
        prices = 15_000 + frame["area_m2"] * 300 + frame["furnished"] * 5_000
        cls.pipeline = model.build_pipeline()
        cls.pipeline.fit(frame[schema.FEATURES], prices)
        cls.metrics = {
            "mae": 1.0,
            "rmse": 2.0,
            "r2": 0.9,
            "avg_price_by_sector": {s: 30_000.0 for s in schema.KNOWN_SECTORS},
        }

    def test_predict_price_returns_float(self):
        from tasador_core import model

        case = dict(model.REFERENCE_INPUTS[0])
        self.assertIsInstance(model.predict_price(self.pipeline, case), float)

    def test_exported_params_reproduce_the_pipeline_exactly(self):
        """The contract that keeps every client port honest."""
        from tasador_core import model

        params = model.export_params(self.pipeline, self.metrics)
        for case in params["reference_cases"]:
            manual = model.predict_from_params(params, case["input"])
            self.assertAlmostEqual(manual, case["expected"], places=6)


if __name__ == "__main__":
    unittest.main()
