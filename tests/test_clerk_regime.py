"""Tests for the deterministic offence-date -> code-regime logic.

The Clerk now requires an explicit, pre-parsed offence date (collected in the
UI/CLI) rather than guessing one from free text. Regime selection is a pure
date comparison; an unparseable date raises rather than silently defaulting.
"""
import unittest
from datetime import date

from agents.clerk import _regime_from_date, _parse_date_strict


class RegimeRoutingTests(unittest.TestCase):
    def test_offence_on_or_after_cutover_is_bns(self):
        self.assertEqual(_regime_from_date(date(2024, 7, 1)), "BNS")
        self.assertEqual(_regime_from_date(date(2024, 11, 22)), "BNS")
        self.assertEqual(_regime_from_date(date(2025, 1, 1)), "BNS")

    def test_offence_before_cutover_is_ipc(self):
        self.assertEqual(_regime_from_date(date(2024, 6, 30)), "IPC")
        self.assertEqual(_regime_from_date(date(2020, 1, 15)), "IPC")
        self.assertEqual(_regime_from_date(date(1999, 12, 31)), "IPC")

    def test_parse_date_accepts_multiple_formats(self):
        self.assertEqual(_parse_date_strict("2024-07-01"), date(2024, 7, 1))
        self.assertEqual(_parse_date_strict("01-07-2024"), date(2024, 7, 1))
        self.assertEqual(_parse_date_strict("1 July 2024"), date(2024, 7, 1))

    def test_parse_date_rejects_ambiguous_input(self):
        # No more silent "grab any 4-digit year" fallback — ambiguous text raises
        # so a malformed date can never misroute BNS/IPC.
        with self.assertRaises(ValueError):
            _parse_date_strict("sometime in 2020")
        with self.assertRaises(ValueError):
            _parse_date_strict("not a date")


if __name__ == "__main__":
    unittest.main()
