"""The guardrail gate — a pre-declared friction ceiling that can
refuse a rollout no matter how strong prevention looks.

A **guardrail metric** is a metric that must not get worse; here it
is the false-action rate on legitimate users (the classifier's false
positives who actually get actioned in the enforcement arm). The
ceiling is declared before the readout — 0.04, four legitimate users
in a hundred actioned — and the gate refuses when:

  REFUSAL 1 — the friction *point estimate* exceeds the ceiling.
              The measured harm to legitimate users is already over
              the line.
  REFUSAL 2 — the point estimate is under the ceiling but the
              interval's *upper bound* is not. The pilot is too
              small to show friction clears the ceiling; "probably
              fine" is not clearance. Widen the holdout / pilot and
              measure again.

Prevention is reported alongside the verdict but never consulted by
it: a gate that strong prevention can override is a dashboard, not
a guardrail.
"""

from __future__ import annotations

from typing import Dict, Sequence

from holdout import estimate_holdout

DEFAULT_FRICTION_CEILING = 0.04


def evaluate_gate(friction: Dict, ceiling: float = DEFAULT_FRICTION_CEILING) -> Dict:
    """Apply the friction gate to a ``proportion_ci`` friction dict."""
    if not 0.0 < ceiling < 1.0:
        raise ValueError("ceiling must be in (0, 1)")
    point = friction["estimate"]
    upper = friction["ci_high"]
    reasons = []
    refused_by = None
    if point is None or point > ceiling:
        refused_by = "friction_exceeds_ceiling"
        reasons.append(
            f"friction point estimate {point} exceeds the pre-declared "
            f"ceiling {ceiling}: too many legitimate users actioned")
    elif upper > ceiling:
        refused_by = "friction_ci_too_wide"
        reasons.append(
            f"friction point estimate {point} is under the ceiling "
            f"{ceiling} but the 95% CI upper bound {upper} is not: "
            "the sample is too small to clear the ceiling")
    return {
        "verdict": "REFUSE" if reasons else "PASS",
        "rollout_allowed": not reasons,
        "refused_by": refused_by,
        "refusal_reasons": reasons,
        "friction_ceiling": ceiling,
        "friction_estimate": point,
        "friction_ci_low": friction["ci_low"],
        "friction_ci_high": upper,
        "friction_ci_width": friction["ci_width"],
    }


def evaluate_stream(rows: Sequence[Dict],
                    ceiling: float = DEFAULT_FRICTION_CEILING) -> Dict:
    """Full readout of one stream: holdout estimate + gate verdict."""
    est = estimate_holdout(rows)
    gate = evaluate_gate(est["friction"], ceiling=ceiling)
    return {"estimate": est, "gate": gate}
