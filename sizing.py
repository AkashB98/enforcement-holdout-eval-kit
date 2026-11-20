"""Holdout sizing — the trade-off the holdout fraction buys.

A holdout is not free: every flagged account in the holdout arm is
an abusive account the platform deliberately does not action, and
some of them go on to cause harm the enforcement arm would have
stopped. A bigger holdout buys a narrower interval on the prevention
estimate; a smaller one lets less abuse through but may leave the
interval so wide the readout cannot decide anything.

The table is a planning calculation at the stream's pooled
unenforced harm rate among flagged accounts (the rate the holdout
arm exists to measure): for each candidate fraction it splits the
flagged cohort analytically and reports the normal-approximation
95% CI width of the per-flagged prevention difference, the width
scaled to the enforcement cohort's prevented total, and the
expected harm-events left unenforced in the holdout arm — the cost
side of the same row. Widths use arm sizes only, so at a fixed
pooled rate they fall monotonically as the fraction approaches
50/50; the evals pin that.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from statsmath import Z_95

DEFAULT_FRACTIONS = (0.01, 0.05, 0.10, 0.25, 0.50)


def sizing_table(rows: Sequence[Dict],
                 fractions: Sequence[float] = DEFAULT_FRACTIONS) -> Dict:
    """CI-width vs holdout-fraction table for one generated stream."""
    flagged = [r for r in rows if r["flagged"]]
    if not flagged:
        raise ValueError("sizing needs at least one flagged account")
    total_flagged = len(flagged)
    pooled_rate = sum(r["harm_if_unenforced"] for r in flagged) / total_flagged
    events_per_harm = (
        sum(r["harm_events_if_unenforced"] for r in flagged)
        / max(1, sum(r["harm_if_unenforced"] for r in flagged)))

    table: List[Dict] = []
    for f in fractions:
        if not 0.0 < f < 1.0:
            raise ValueError("holdout fractions must be in (0, 1)")
        n_hold = round(total_flagged * f)
        n_enf = total_flagged - n_hold
        if n_hold <= 0 or n_enf <= 0:
            raise ValueError("fraction leaves an empty arm at this cohort size")
        se = math.sqrt(pooled_rate * (1.0 - pooled_rate)
                       * (1.0 / n_hold + 1.0 / n_enf))
        width = 2.0 * Z_95 * se
        table.append({
            "holdout_fraction": f,
            "flagged_holdout": n_hold,
            "flagged_enforcement": n_enf,
            "ci_width_per_flagged": round(width, 6),
            "ci_width_total": round(width * n_enf, 6),
            "expected_harm_left_unenforced": round(n_hold * pooled_rate, 6),
            "expected_harm_events_left_unenforced": round(
                n_hold * pooled_rate * events_per_harm, 6),
        })
    return {
        "flagged_total": total_flagged,
        "pooled_harm_rate_flagged": round(pooled_rate, 6),
        "rows": table,
    }
