import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import (arm_counts, generate_scenario, generate_stream,  # noqa: E402
                       rows_to_csv, rows_to_jsonl)


class TestGenerator(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(generate_scenario("clean"), generate_scenario("clean"))

    def test_seed_changes_data(self):
        self.assertNotEqual(generate_scenario("clean", seed=1),
                            generate_scenario("clean", seed=2))

    def test_shape_and_fields(self):
        rows = generate_scenario("clean")
        self.assertEqual(len(rows), 10000)
        for r in rows[:50]:
            self.assertEqual(set(r), {
                "account_id", "true_type", "risk_score", "flagged",
                "would_churn", "arm", "actioned", "harm_if_unenforced",
                "harm_events_if_unenforced", "harm_observed",
                "harm_events_observed"})
            self.assertIn(r["arm"], ("enforcement", "holdout"))
            self.assertIn(r["true_type"], ("abusive", "legitimate"))

    def test_account_ids_unique(self):
        rows = generate_scenario("clean")
        self.assertEqual(len({r["account_id"] for r in rows}), 10000)

    def test_actioned_means_flagged_and_enforcement(self):
        for r in generate_scenario("clean"):
            self.assertEqual(r["actioned"],
                             r["flagged"] and r["arm"] == "enforcement")

    def test_observed_harm_consistency(self):
        for r in generate_scenario("clean"):
            if r["actioned"]:
                self.assertEqual(r["harm_observed"], 0)
            else:
                self.assertEqual(r["harm_observed"], r["harm_if_unenforced"])

    def test_churn_only_abusive_and_never_harms(self):
        for r in generate_scenario("clean"):
            if r["would_churn"]:
                self.assertEqual(r["true_type"], "abusive")
                self.assertEqual(r["harm_if_unenforced"], 0)
            if r["true_type"] == "legitimate":
                self.assertEqual(r["harm_if_unenforced"], 0)
                self.assertFalse(r["would_churn"])

    def test_planted_prevalence_and_churn_near_targets(self):
        rows = generate_scenario("clean")
        prev = sum(r["true_type"] == "abusive" for r in rows) / len(rows)
        self.assertTrue(0.09 < prev < 0.11, prev)
        flagged_ab = [r for r in rows
                      if r["flagged"] and r["true_type"] == "abusive"]
        churn = sum(r["would_churn"] for r in flagged_ab) / len(flagged_ab)
        self.assertTrue(0.34 < churn < 0.46, churn)

    def test_holdout_fraction_near_default(self):
        counts = arm_counts(generate_scenario("clean"))
        share = counts["holdout"] / sum(counts.values())
        self.assertTrue(0.08 < share < 0.12, share)

    def test_wide_ci_scenario_shape(self):
        rows = generate_scenario("wide_ci")
        self.assertEqual(len(rows), 240)
        counts = arm_counts(rows)
        self.assertTrue(0.4 < counts["holdout"] / 240 < 0.6)

    def test_csv_round_trip_shape(self):
        text = rows_to_csv(generate_scenario("clean", n_accounts=20))
        lines = text.strip().splitlines()
        self.assertEqual(len(lines), 21)
        self.assertTrue(lines[0].startswith("account_id,true_type,"))

    def test_jsonl_md5_stable_across_calls(self):
        a = hashlib.md5(rows_to_jsonl(generate_scenario("clean")).encode()).hexdigest()
        b = hashlib.md5(rows_to_jsonl(generate_scenario("clean")).encode()).hexdigest()
        self.assertEqual(a, b)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            generate_scenario("nope")
        with self.assertRaises(ValueError):
            generate_stream(n_accounts=5)
        with self.assertRaises(ValueError):
            generate_stream(holdout_fraction=1.0)
        with self.assertRaises(ValueError):
            generate_stream(abuse_prevalence=0.0)


if __name__ == "__main__":
    unittest.main()
