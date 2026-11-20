import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report import build_report  # noqa: E402


class TestReport(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(build_report(), build_report())

    def test_structure_and_scenario_verdicts(self):
        rep = build_report()
        self.assertEqual(rep["dataset"]["rows"], 10000)
        self.assertTrue(rep["dataset"]["synthetic"])
        self.assertEqual(rep["scenarios"]["clean"]["gate"]["verdict"], "PASS")
        self.assertEqual(rep["scenarios"]["high_friction"]["gate"]["verdict"],
                         "REFUSE")
        self.assertEqual(rep["scenarios"]["wide_ci"]["gate"]["verdict"],
                         "REFUSE")
        self.assertEqual(rep["clean"], rep["scenarios"]["clean"])

    def test_classifier_summary_consistent(self):
        rep = build_report()
        c = rep["classifier"]
        self.assertEqual(c["true_positives"] + c["false_negatives"],
                         c["abusive_ground_truth"])
        self.assertEqual(c["true_positives"] + c["false_positives"],
                         c["flagged"])
        self.assertEqual(c["ruleset_version"], "v1-frozen")


if __name__ == "__main__":
    unittest.main()
