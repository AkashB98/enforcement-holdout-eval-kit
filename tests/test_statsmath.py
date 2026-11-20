import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from statsmath import Z_95, difference_ci, proportion_ci, z_for_confidence  # noqa: E402


class TestStatsmath(unittest.TestCase):
    def test_z95_pinned(self):
        self.assertEqual(Z_95, 1.959964)
        self.assertAlmostEqual(z_for_confidence(0.95), Z_95, places=6)

    def test_proportion_hand_case(self):
        ci = proportion_ci(50, 100)
        self.assertEqual(ci["estimate"], 0.5)
        self.assertAlmostEqual(ci["ci_low"], 0.402, places=3)
        self.assertAlmostEqual(ci["ci_high"], 0.598, places=3)

    def test_proportion_clipped(self):
        ci = proportion_ci(99, 100)
        self.assertLessEqual(ci["ci_high"], 1.0)
        ci0 = proportion_ci(0, 100)
        self.assertEqual(ci0["ci_low"], 0.0)
        self.assertEqual(ci0["estimate"], 0.0)

    def test_proportion_zero_n_is_full_range(self):
        ci = proportion_ci(0, 0)
        self.assertIsNone(ci["estimate"])
        self.assertEqual((ci["ci_low"], ci["ci_high"]), (0.0, 1.0))

    def test_proportion_invalid(self):
        with self.assertRaises(ValueError):
            proportion_ci(5, 4)

    def test_difference_hand_case(self):
        d = difference_ci(0, 100, 50, 100)
        self.assertEqual(d["difference"], 0.5)
        self.assertAlmostEqual(d["se"], 0.05, places=6)
        self.assertLess(d["ci_low"], 0.5)
        self.assertGreater(d["ci_high"], 0.5)

    def test_difference_zero_variance_arm(self):
        d = difference_ci(0, 200, 0, 200)
        self.assertEqual(d["difference"], 0.0)
        self.assertEqual(d["ci_width"], 0.0)

    def test_difference_sign_convention(self):
        d = difference_ci(80, 100, 20, 100)
        self.assertEqual(d["difference"], -0.6)

    def test_confidence_validated(self):
        with self.assertRaises(ValueError):
            z_for_confidence(1.0)


if __name__ == "__main__":
    unittest.main()
