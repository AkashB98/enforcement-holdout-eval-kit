import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import FLAG_THRESHOLD, RULESET_VERSION, classify_rows, is_flagged  # noqa: E402
from generator import generate_scenario  # noqa: E402
from helpers import row  # noqa: E402


class TestClassifier(unittest.TestCase):
    def test_threshold_is_frozen_value(self):
        self.assertEqual(FLAG_THRESHOLD, 0.65)
        self.assertEqual(RULESET_VERSION, "v1-frozen")

    def test_boundary(self):
        self.assertTrue(is_flagged(0.65))
        self.assertTrue(is_flagged(1.0))
        self.assertFalse(is_flagged(0.6499))
        self.assertFalse(is_flagged(0.0))

    def test_score_range_validated(self):
        with self.assertRaises(ValueError):
            is_flagged(1.01)
        with self.assertRaises(ValueError):
            is_flagged(-0.01)

    def test_generator_agrees_with_ruleset(self):
        for r in generate_scenario("clean", n_accounts=200):
            self.assertEqual(r["flagged"], is_flagged(r["risk_score"]))

    def test_seeded_recall_and_fpr_ranges(self):
        rows = generate_scenario("clean")
        abusive = [r for r in rows if r["true_type"] == "abusive"]
        legit = [r for r in rows if r["true_type"] == "legitimate"]
        recall = sum(r["flagged"] for r in abusive) / len(abusive)
        fpr = sum(r["flagged"] for r in legit) / len(legit)
        self.assertTrue(0.75 < recall < 0.85, recall)
        self.assertTrue(0.015 < fpr < 0.03, fpr)

    def test_classify_rows_hand_built(self):
        rows = [row(flagged=True, true_type="abusive"),
                row(account_id="acct_00002", flagged=True),
                row(account_id="acct_00003", flagged=False,
                    true_type="abusive")]
        self.assertEqual(classify_rows(rows), (2, 1, 1))


if __name__ == "__main__":
    unittest.main()
