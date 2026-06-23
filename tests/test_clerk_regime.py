"""Tests for the deterministic offence-date -> code-regime logic."""
import unittest

from agents.clerk import _determine_regime, _parse_date


class RegimeRoutingTests(unittest.TestCase):
    def test_offence_on_or_after_cutover_is_bns(self):
        self.assertEqual(_determine_regime("2024-07-01"), "BNS")
        self.assertEqual(_determine_regime("2024-11-22"), "BNS")
        self.assertEqual(_determine_regime("2025-01-01"), "BNS")

    def test_offence_before_cutover_is_ipc(self):
        self.assertEqual(_determine_regime("2024-06-30"), "IPC")
        self.assertEqual(_determine_regime("2020-01-15"), "IPC")
        self.assertEqual(_determine_regime("1999-12-31"), "IPC")

    def test_unknown_date_defaults_to_bns(self):
        self.assertEqual(_determine_regime(None), "BNS")
        self.assertEqual(_determine_regime(""), "BNS")

    def test_parse_date_accepts_multiple_formats(self):
        self.assertIsNotNone(_parse_date("2024-07-01"))
        self.assertIsNotNone(_parse_date("01-07-2024"))
        self.assertIsNotNone(_parse_date("1 July 2024"))

    def test_parse_date_falls_back_to_year(self):
        d = _parse_date("sometime in 2020")
        self.assertIsNotNone(d)
        self.assertEqual(d.year, 2020)


if __name__ == "__main__":
    unittest.main()
