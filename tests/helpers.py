"""Shared row builders for the test suite (not a test module)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def row(account_id="acct_00001", true_type="legitimate", risk_score=0.30,
        flagged=False, would_churn=False, arm="enforcement",
        actioned=False, harm_if_unenforced=0, harm_events_if_unenforced=0,
        harm_observed=None, harm_events_observed=None):
    if harm_observed is None:
        harm_observed = 0 if actioned else harm_if_unenforced
    if harm_events_observed is None:
        harm_events_observed = 0 if actioned else harm_events_if_unenforced
    return {"account_id": account_id, "true_type": true_type,
            "risk_score": risk_score, "flagged": flagged,
            "would_churn": would_churn, "arm": arm, "actioned": actioned,
            "harm_if_unenforced": harm_if_unenforced,
            "harm_events_if_unenforced": harm_events_if_unenforced,
            "harm_observed": harm_observed,
            "harm_events_observed": harm_events_observed}


def flagged_pair(n_flagged_per_arm=100, harm_rate_holdout=0.5,
                 fp_per_enf_legit=0, legit_enf=100):
    """Deterministic hand-built flagged cohort + enforcement legit rows.

    Flagged abusive accounts: enforcement-arm ones are actioned (no
    observed harm); holdout-arm ones harm at ``harm_rate_holdout``
    (first that share of them). Plus ``legit_enf`` legitimate
    enforcement-arm accounts, the first ``fp_per_enf_legit`` flagged.
    """
    rows = []
    i = 0

    def nid():
        nonlocal i
        i += 1
        return f"acct_{i:05d}"

    for _ in range(n_flagged_per_arm):
        rows.append(row(nid(), "abusive", 0.90, True, False,
                        "enforcement", True, 1, 2))
    n_harm = int(n_flagged_per_arm * harm_rate_holdout)
    for j in range(n_flagged_per_arm):
        harm = 1 if j < n_harm else 0
        rows.append(row(nid(), "abusive", 0.90, True, harm == 0,
                        "holdout", False, harm, 2 * harm))
    for j in range(legit_enf):
        flagged = j < fp_per_enf_legit
        rows.append(row(nid(), "legitimate", 0.90 if flagged else 0.30,
                        flagged, False, "enforcement", flagged, 0, 0))
    return rows
