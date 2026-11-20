import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import generate_scenario  # noqa: E402
from helpers import flagged_pair  # noqa: E402
from holdout import estimate_holdout  # noqa: E402


class TestHoldout(unittest.TestCase):
    def test_hand_built_exact(self):
        # 100 flagged per arm; holdout harms at 0.5, enforcement at 0.
        est = estimate_holdout(flagged_pair(100, 0.5))
        self.assertEqual(est["harm_rate_holdout_flagged"], 0.5)
        self.assertEqual(est["harm_rate_enforcement_flagged"], 0.0)
        self.assertEqual(est["causal_prevented"]["per_flagged"], 0.5)
        self.assertEqual(est["causal_prevented"]["total"], 50.0)
        self.assertEqual(est["naive_prevented"], 100)
        self.assertEqual(est["overstatement"], 50.0)
        self.assertEqual(est["overstatement_share_of_naive"], 0.5)
        self.assertEqual(est["true_prevented_ground_truth"], 100)

    def test_hand_built_friction(self):
        est = estimate_holdout(flagged_pair(100, 0.5, fp_per_enf_legit=3,
                                            legit_enf=100))
        self.assertEqual(est["friction"]["false_actions"], 3)
        self.assertEqual(est["friction"]["estimate"], 0.03)

    def test_clean_naive_exceeds_causal_by_churn_share(self):
        est = estimate_holdout(generate_scenario("clean"))
        self.assertGreater(est["naive_prevented"],
                           est["causal_prevented"]["total"])
        self.assertAlmostEqual(est["overstatement_share_of_naive"],
                               est["churn_share_flagged_abusive"],
                               delta=0.08)
        self.assertAlmostEqual(est["overstatement_share_of_naive"], 0.40,
                               delta=0.08)

    def test_clean_causal_ci_covers_ground_truth(self):
        est = estimate_holdout(generate_scenario("clean"))
        self.assertLessEqual(est["causal_prevented"]["ci_low"],
                             est["true_prevented_ground_truth"])
        self.assertLessEqual(est["true_prevented_ground_truth"],
                             est["causal_prevented"]["ci_high"])

    def test_no_churn_no_overstatement(self):
        from generator import generate_stream
        est = estimate_holdout(generate_stream(churn_share=0.0))
        self.assertAlmostEqual(est["overstatement_share_of_naive"], 0.0,
                               delta=0.08)

    def test_full_churn_all_overstatement(self):
        from generator import generate_stream
        est = estimate_holdout(generate_stream(churn_share=1.0))
        self.assertEqual(est["causal_prevented"]["total"], 0.0)
        self.assertEqual(est["overstatement_share_of_naive"], 1.0)

    def test_missing_arm_raises(self):
        rows = [r for r in generate_scenario("clean")
                if r["arm"] == "enforcement"]
        with self.assertRaises(ValueError):
            estimate_holdout(rows)


if __name__ == "__main__":
    unittest.main()
