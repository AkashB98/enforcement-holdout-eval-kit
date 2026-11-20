import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gate import evaluate_gate, evaluate_stream  # noqa: E402
from generator import generate_scenario  # noqa: E402
from statsmath import proportion_ci  # noqa: E402


def _friction(point, low, high):
    return {"estimate": point, "ci_low": low, "ci_high": high,
            "ci_width": round(high - low, 6), "n": 1000, "successes": 0,
            "se": 0.01, "false_actions": 0}


class TestGate(unittest.TestCase):
    def test_pass_when_point_and_bound_clear(self):
        g = evaluate_gate(_friction(0.02, 0.015, 0.025))
        self.assertEqual(g["verdict"], "PASS")
        self.assertTrue(g["rollout_allowed"])
        self.assertIsNone(g["refused_by"])

    def test_refuse_point_over_ceiling(self):
        g = evaluate_gate(_friction(0.15, 0.14, 0.16))
        self.assertEqual(g["verdict"], "REFUSE")
        self.assertEqual(g["refused_by"], "friction_exceeds_ceiling")

    def test_refuse_wide_ci_only(self):
        g = evaluate_gate(_friction(0.02, 0.0, 0.06))
        self.assertEqual(g["verdict"], "REFUSE")
        self.assertEqual(g["refused_by"], "friction_ci_too_wide")

    def test_point_exactly_at_ceiling_passes_if_bound_clears(self):
        # Point equal to the ceiling does not exceed it; bound equal
        # clears it. (Seeded scenarios never sit on the line.)
        g = evaluate_gate(_friction(0.04, 0.03, 0.04))
        self.assertEqual(g["verdict"], "PASS")

    def test_undefined_estimate_refuses(self):
        g = evaluate_gate(proportion_ci(0, 0))
        self.assertEqual(g["verdict"], "REFUSE")
        self.assertEqual(g["refused_by"], "friction_exceeds_ceiling")

    def test_ceiling_validated(self):
        with self.assertRaises(ValueError):
            evaluate_gate(_friction(0.01, 0.0, 0.02), ceiling=1.0)

    def test_seeded_scenarios(self):
        clean = evaluate_stream(generate_scenario("clean"))
        self.assertEqual(clean["gate"]["verdict"], "PASS")
        hf = evaluate_stream(generate_scenario("high_friction"))
        self.assertEqual(hf["gate"]["verdict"], "REFUSE")
        self.assertEqual(hf["gate"]["refused_by"], "friction_exceeds_ceiling")
        wc = evaluate_stream(generate_scenario("wide_ci"))
        self.assertEqual(wc["gate"]["verdict"], "REFUSE")
        self.assertEqual(wc["gate"]["refused_by"], "friction_ci_too_wide")

    def test_prevention_never_overrides_friction(self):
        # High-friction scenario still prevents real abuse; the gate
        # refuses anyway — prevention is not an input to the verdict.
        hf = evaluate_stream(generate_scenario("high_friction"))
        self.assertGreater(hf["estimate"]["causal_prevented"]["total"], 0)
        self.assertEqual(hf["gate"]["verdict"], "REFUSE")


if __name__ == "__main__":
    unittest.main()
