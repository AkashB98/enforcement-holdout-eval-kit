import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import generate_scenario  # noqa: E402
from sizing import DEFAULT_FRACTIONS, sizing_table  # noqa: E402


class TestSizing(unittest.TestCase):
    def setUp(self):
        self.table = sizing_table(generate_scenario("clean"))

    def test_fractions_pinned(self):
        self.assertEqual([r["holdout_fraction"] for r in self.table["rows"]],
                         list(DEFAULT_FRACTIONS))
        self.assertEqual(list(DEFAULT_FRACTIONS),
                         [0.01, 0.05, 0.10, 0.25, 0.50])

    def test_ci_width_monotonically_decreases(self):
        widths = [r["ci_width_per_flagged"] for r in self.table["rows"]]
        self.assertTrue(all(b < a for a, b in zip(widths, widths[1:])), widths)
        totals = [r["ci_width_total"] for r in self.table["rows"]]
        self.assertTrue(all(b < a for a, b in zip(totals, totals[1:])), totals)

    def test_harm_left_unenforced_increases(self):
        harm = [r["expected_harm_left_unenforced"] for r in self.table["rows"]]
        self.assertTrue(all(b > a for a, b in zip(harm, harm[1:])), harm)

    def test_arm_sizes_sum_to_flagged_total(self):
        for r in self.table["rows"]:
            self.assertEqual(r["flagged_holdout"] + r["flagged_enforcement"],
                             self.table["flagged_total"])

    def test_invalid_fraction(self):
        rows = generate_scenario("clean")
        with self.assertRaises(ValueError):
            sizing_table(rows, fractions=(0.0,))
        with self.assertRaises(ValueError):
            sizing_table(rows, fractions=(1.0,))

    def test_no_flagged_raises(self):
        from helpers import row
        with self.assertRaises(ValueError):
            sizing_table([row()])


if __name__ == "__main__":
    unittest.main()
