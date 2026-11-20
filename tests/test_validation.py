import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import generate_scenario  # noqa: E402
from helpers import row  # noqa: E402
from validation import validate_dataset  # noqa: E402


def _pair():
    return [row(arm="enforcement"),
            row(account_id="acct_00002", arm="holdout")]


class TestValidation(unittest.TestCase):
    def test_generated_data_is_clean(self):
        self.assertEqual(validate_dataset(generate_scenario("clean")), [])
        self.assertEqual(validate_dataset(generate_scenario("wide_ci")), [])

    def test_empty(self):
        self.assertEqual(validate_dataset([]), ["dataset is empty"])

    def test_missing_field(self):
        rows = _pair()
        del rows[0]["arm"]
        self.assertTrue(any("missing" in i for i in validate_dataset(rows)))

    def test_duplicate_ids(self):
        rows = _pair()
        rows[1]["account_id"] = rows[0]["account_id"]
        self.assertTrue(any("duplicate" in i for i in validate_dataset(rows)))

    def test_unknown_arm_and_type(self):
        rows = _pair()
        rows[0]["arm"] = "shadow"
        rows[1]["true_type"] = "bot"
        issues = validate_dataset(rows)
        self.assertTrue(any("unknown arm" in i for i in issues))
        self.assertTrue(any("unknown true_type" in i for i in issues))

    def test_bool_trap(self):
        rows = _pair()
        rows[0]["flagged"] = 1
        self.assertTrue(any("must be a bool" in i
                            for i in validate_dataset(rows)))

    def test_actioned_with_harm_flagged(self):
        rows = _pair()
        rows[0].update({"flagged": True, "actioned": True,
                        "harm_if_unenforced": 1, "harm_observed": 1})
        self.assertTrue(any("actioned" in i for i in validate_dataset(rows)))

    def test_unactioned_harm_mismatch(self):
        rows = _pair()
        rows[0].update({"harm_if_unenforced": 1, "harm_observed": 0})
        self.assertTrue(any("unactioned" in i for i in validate_dataset(rows)))

    def test_single_arm_rejected(self):
        rows = [row(), row(account_id="acct_00002")]
        self.assertTrue(any("both arms" in i for i in validate_dataset(rows)))


if __name__ == "__main__":
    unittest.main()
