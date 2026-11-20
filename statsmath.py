"""Small statistical primitives, stdlib only.

Only what the holdout estimator and the guardrail gate need:

- a normal quantile (via ``statistics.NormalDist``) for 95% intervals,
- a Wald (normal-approximation) confidence interval for a proportion,
- a Wald interval for a difference of two proportions.

The intervals are deliberately the textbook ones: this kit is an audit
artifact, and an interval anyone can recompute by hand from the printed
counts is worth more than a cleverer one nobody checks. Proportions
are clipped into [0, 1] after the interval is formed; differences are
not clipped.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_NORM = NormalDist()

Z_95 = 1.959964  # NormalDist().inv_cdf(0.975), pinned by an eval


def z_for_confidence(confidence: float = 0.95) -> float:
    """Two-sided standard-normal critical value for ``confidence``."""
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    return _NORM.inv_cdf(0.5 + confidence / 2.0)


def proportion_ci(successes: int, n: int, confidence: float = 0.95) -> dict:
    """Wald CI for a binomial proportion.

    Returns the point estimate plus ``ci_low`` / ``ci_high`` (clipped to
    [0, 1]) and ``ci_width`` (the clipped width, so it is the width a
    reader sees). With n == 0 the estimate is undefined: the interval
    is the whole [0, 1] range, which can never clear any ceiling — the
    conservative answer for a guardrail gate.
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("need 0 <= successes <= n")
    z = z_for_confidence(confidence)
    if n == 0:
        return {"estimate": None, "n": 0, "successes": successes,
                "ci_low": 0.0, "ci_high": 1.0, "ci_width": 1.0,
                "se": None}
    p = successes / n
    se = math.sqrt(p * (1.0 - p) / n)
    low = max(0.0, p - z * se)
    high = min(1.0, p + z * se)
    return {"estimate": round(p, 6), "n": n, "successes": successes,
            "ci_low": round(low, 6), "ci_high": round(high, 6),
            "ci_width": round(high - low, 6), "se": round(se, 6)}


def difference_ci(succ_a: int, n_a: int, succ_b: int, n_b: int,
                  confidence: float = 0.95) -> dict:
    """Wald CI for p_b - p_a (two independent proportions).

    Arm A is the first (baseline) arm, arm B the second; the reported
    difference is B minus A. Zero-variance arms (an enforcement arm in
    which actioned actors cause no observed harm, so the rate is
    identically 0) contribute zero to the standard error — that is the
    correct arithmetic for a constant, not a special case.
    """
    for s, n in ((succ_a, n_a), (succ_b, n_b)):
        if n <= 0 or s < 0 or s > n:
            raise ValueError("need 0 <= successes <= n and n > 0")
    z = z_for_confidence(confidence)
    pa, pb = succ_a / n_a, succ_b / n_b
    diff = pb - pa
    se = math.sqrt(pa * (1.0 - pa) / n_a + pb * (1.0 - pb) / n_b)
    return {"rate_a": round(pa, 6), "rate_b": round(pb, 6),
            "difference": round(diff, 6),
            "ci_low": round(diff - z * se, 6),
            "ci_high": round(diff + z * se, 6),
            "ci_width": round(2.0 * z * se, 6), "se": round(se, 6)}
