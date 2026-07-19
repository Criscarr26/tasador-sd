"""Guards the sitemap discovery filter (services/listings-agent/discovery.py).

The filter is the legal boundary of collection: it must only produce
apartment DETAIL pages in sectors the model knows, and never anything
under /buscar/ (disallowed by SuperCasas robots.txt). These tests pin
that contract with real URL shapes from the 2026-07-12 sitemap survey.

Run from the repo root (discovery's pure functions import only the
stdlib and tasador-core, so this needs none of the agent's HTTP deps):
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "listings-agent"))

import discovery  # noqa: E402
from tasador_core import schema  # noqa: E402

FIXTURE = ROOT / "services" / "listings-agent" / "data" / "samples" / "sitemap_sample.xml"


class TestSectorSlugs(unittest.TestCase):
    def test_every_model_sector_produces_a_slug(self):
        slugs = discovery.sector_slugs()
        for sector in schema.KNOWN_SECTORS:
            expected = discovery._slugify(sector)
            self.assertIn(expected, slugs, f"missing slug for {sector}")

    def test_site_specific_naco_variant_is_included(self):
        # SuperCasas publishes Naco as 'ensanche-naco' (plain 'naco'
        # does not occur in the sitemap).
        self.assertIn("ensanche-naco", discovery.sector_slugs())

    def test_accents_are_stripped(self):
        self.assertEqual(discovery._slugify("Serrallés"), "serralles")


class TestFilterCandidates(unittest.TestCase):
    def test_accepts_apartment_detail_pages_in_known_sectors(self):
        accepted = discovery.filter_candidates(
            [
                "https://www.supercasas.com/apartamentos-piantini/1390001/",
                "https://www.supercasas.com/apartamentos-ensanche-naco/1383439/",
                "https://www.supercasas.com/apartamentos-bella-vista/1390002/",
            ]
        )
        self.assertEqual(len(accepted), 3)

    def test_rejects_other_property_types(self):
        # The model is trained on apartments; anything else is fetch
        # budget spent on guaranteed skips.
        self.assertEqual(
            discovery.filter_candidates(
                [
                    "https://www.supercasas.com/casas-bella-vista/1390007/",
                    "https://www.supercasas.com/penthouse-piantini/1390008/",
                    "https://www.supercasas.com/locales-comerciales-piantini/1390009/",
                ]
            ),
            [],
        )

    def test_rejects_unknown_and_sub_sectors(self):
        # Sub-sector variants would be rejected by normalize_sector at
        # save time; filtering them here saves the fetch.
        self.assertEqual(
            discovery.filter_candidates(
                [
                    "https://www.supercasas.com/apartamentos-bella-vista-sur/1390005/",
                    "https://www.supercasas.com/apartamentos-arroyo-hondo-viejo/1390006/",
                    "https://www.supercasas.com/apartamentos-evaristo-morales/1383435/",
                ]
            ),
            [],
        )

    def test_rejects_non_detail_urls(self):
        self.assertEqual(
            discovery.filter_candidates(
                [
                    "https://www.supercasas.com/propiedades/remax-inmobiliaria",
                    "https://www.supercasas.com/directorio/inmobiliarias/0",
                    "https://www.supercasas.com/buscar/?PriceType=400",
                    "https://www.supercasas.com/apartamentos-piantini/not-a-number/",
                ]
            ),
            [],
        )

    def test_never_lets_a_disallowed_path_through(self):
        # /buscar/ and /buscador/ are Disallowed in robots.txt; the
        # filter must be structurally unable to emit them.
        for url in [
            "https://www.supercasas.com/buscar/123/",
            "https://www.supercasas.com/buscador/456/",
        ]:
            self.assertEqual(discovery.filter_candidates([url]), [])


class TestParseSitemap(unittest.TestCase):
    def test_parses_the_bundled_fixture(self):
        urls = discovery.parse_sitemap(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(urls), 13)
        self.assertIn("https://www.supercasas.com/apartamentos-piantini/1390001/", urls)

    def test_fixture_filters_to_known_sector_apartments_only(self):
        urls = discovery.parse_sitemap(FIXTURE.read_text(encoding="utf-8"))
        accepted = discovery.filter_candidates(urls)
        self.assertEqual(
            accepted,
            [
                "https://www.supercasas.com/apartamentos-ensanche-naco/1383439/",
                "https://www.supercasas.com/apartamentos-piantini/1390001/",
                "https://www.supercasas.com/apartamentos-bella-vista/1390002/",
                "https://www.supercasas.com/apartamentos-serralles/1390003/",
                "https://www.supercasas.com/apartamentos-gazcue/1390004/",
            ],
        )


if __name__ == "__main__":
    unittest.main()
