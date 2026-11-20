"""The holdout estimator — what enforcement actually caused.

The naive headline counts every actioned abusive account as abuse
prevented. That assumes each of them would have gone on to cause
harm. The randomised holdout tests the assumption: flagged accounts
in the holdout arm are *not* actioned, so the harm they go on to
cause is directly observable, and the enforcement arm's flagged
accounts show the harm that remains under enforcement (zero, for
actioned accounts, in this model).

    causal prevented per flagged account
        = harm rate among flagged, holdout arm
          - harm rate among flagged, enforcement arm
    causal prevented (total, enforcement cohort)
        = that difference x flagged accounts in the enforcement arm

The naive figure needs the synthetic ground truth (the count of
actioned *abusive* accounts); the causal figure does not — it is
computed from observed harm on the flagged cohort alone, and the
false-positive dilution in the flagged cohort cancels when the
per-flagged difference is scaled back up to the enforcement cohort.
That is the point of a holdout: the estimable number and the true
number are the same number, up to sampling error the interval
reports honestly.
"""

from __future__ import annotations

from typing import Dict, Sequence

from statsmath import difference_ci, proportion_ci


def estimate_holdout(rows: Sequence[Dict]) -> Dict:
    """Causal prevention + friction estimates from one stream."""
    flagged = [r for r in rows if r["flagged"]]
    enf = [r for r in flagged if r["arm"] == "enforcement"]
    hold = [r for r in flagged if r["arm"] == "holdout"]
    if not enf or not hold:
        raise ValueError("holdout estimate needs flagged accounts in both arms")

    harm_enf = sum(r["harm_observed"] for r in enf)
    harm_hold = sum(r["harm_observed"] for r in hold)
    diff = difference_ci(harm_enf, len(enf), harm_hold, len(hold))
    n_enf = len(enf)
    causal = {
        "per_flagged": diff["difference"],
        "ci_low_per_flagged": diff["ci_low"],
        "ci_high_per_flagged": diff["ci_high"],
        "ci_width_per_flagged": diff["ci_width"],
        "total": round(diff["difference"] * n_enf, 6),
        "ci_low": round(diff["ci_low"] * n_enf, 6),
        "ci_high": round(diff["ci_high"] * n_enf, 6),
        "ci_width": round(diff["ci_width"] * n_enf, 6),
    }

    # Naive headline (ground truth): actioned abusive accounts,
    # each counted as one unit of abuse prevented.
    actioned = [r for r in rows if r["actioned"]]
    tp_actioned = sum(1 for r in actioned if r["true_type"] == "abusive")
    naive = tp_actioned
    over = round(naive - causal["total"], 6)
    over_share = round(over / naive, 6) if naive else 0.0

    # Ground-truth truth-check (synthetic only): how many of the
    # actioned abusive accounts really would have caused harm.
    true_prevented = sum(r["harm_if_unenforced"] for r in actioned
                         if r["true_type"] == "abusive")
    flagged_abusive = [r for r in flagged if r["true_type"] == "abusive"]
    churn_share = (round(sum(r["would_churn"] for r in flagged_abusive)
                         / len(flagged_abusive), 6)
                   if flagged_abusive else 0.0)

    # Friction on the same split: legitimate accounts in the
    # enforcement arm who were flagged (and therefore actioned).
    leg_enf = [r for r in rows
               if r["arm"] == "enforcement" and r["true_type"] == "legitimate"]
    fp_enf = sum(1 for r in leg_enf if r["flagged"])
    friction = proportion_ci(fp_enf, len(leg_enf))
    friction["false_actions"] = fp_enf

    return {
        "flagged_total": len(flagged),
        "flagged_enforcement": n_enf,
        "flagged_holdout": len(hold),
        "harm_rate_enforcement_flagged": diff["rate_a"],
        "harm_rate_holdout_flagged": diff["rate_b"],
        "causal_prevented": causal,
        "naive_prevented": naive,
        "naive_actions_total": len(actioned),
        "overstatement": over,
        "overstatement_share_of_naive": over_share,
        "true_prevented_ground_truth": true_prevented,
        "churn_share_flagged_abusive": churn_share,
        "friction": friction,
    }
