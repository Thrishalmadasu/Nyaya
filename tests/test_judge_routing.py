"""Tests for the deterministic win-probability and early-exit threshold.

These are pure-math checks (no LLM, no corpus) for the logic that decides when a
trial is decisively one-sided and should end early. A test like this would have
caught the "every case runs to the cap" bug, where the threshold was set so high
the early-exit never fired.
"""
import unittest

from agents.judge import win_probability, _EARLY_EXIT_WP, _WIN_PROB_MARGIN_SCALE


def _exits_early(wp: int) -> bool:
    return wp >= _EARLY_EXIT_WP or wp <= 100 - _EARLY_EXIT_WP


class WinProbabilityTests(unittest.TestCase):
    def test_even_case_is_fifty(self):
        self.assertEqual(win_probability(5, 5), 50)

    def test_prosecution_lead_raises_probability(self):
        # 8 vs 5 → +3 margin → 50 + 3*7 = 71
        self.assertEqual(win_probability(8, 5), 71)

    def test_defence_lead_lowers_probability(self):
        self.assertEqual(win_probability(5, 8), 29)

    def test_clamped_to_5_95(self):
        self.assertEqual(win_probability(10, 1), 95)
        self.assertEqual(win_probability(1, 10), 5)


class EarlyExitThresholdTests(unittest.TestCase):
    def test_close_case_keeps_arguing(self):
        # within ~2 points → no early exit, the contest stays live
        self.assertFalse(_exits_early(win_probability(6, 5)))   # 57
        self.assertFalse(_exits_early(win_probability(5, 6)))   # 43
        self.assertFalse(_exits_early(win_probability(7, 5)))   # 64 (2-pt lead)

    def test_clear_lead_exits_early(self):
        # a clear ~3-point lead is decisive and ends the trial
        self.assertTrue(_exits_early(win_probability(8, 5)))    # 71 (prosecution)
        self.assertTrue(_exits_early(win_probability(5, 8)))    # 29 (defence)

    def test_threshold_is_reachable(self):
        # Regression guard: the margin needed to exit must be modest (~2.9 pts),
        # not the old ~4.3 that made early-exit effectively unreachable.
        margin_needed = (_EARLY_EXIT_WP - 50) / _WIN_PROB_MARGIN_SCALE
        self.assertLessEqual(margin_needed, 3.0)


if __name__ == "__main__":
    unittest.main()
