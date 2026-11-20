"""The frozen classifier — a fixed ruleset, never tuned here.

SYNTHETIC DATA ONLY. Fernline is a fictional social platform and the
risk scores it assigns are fabricated by the seeded generator.

The ruleset is one line, versioned and frozen for the whole kit:

    flagged  <=>  risk_score >= 0.65        (RULESET_VERSION v1-frozen)

There is deliberately **no** threshold search, no precision/recall
sweep, and no parameter that any code path in this kit adjusts:
tuning a detection threshold against an outcome is a different job
(a sibling kit covers rule tuning). This kit takes the classifier as
given — exactly as an enforcement-measurement team inherits whatever
the detection team shipped — and asks what its enforcement actually
causes, and what it costs legitimate users.
"""

from __future__ import annotations

RULESET_VERSION = "v1-frozen"
FLAG_THRESHOLD = 0.65


def is_flagged(risk_score: float) -> bool:
    """Apply the frozen ruleset to one account's risk score."""
    if not 0.0 <= risk_score <= 1.0:
        raise ValueError("risk_score must be in [0, 1]")
    return risk_score >= FLAG_THRESHOLD


def classify_rows(rows):
    """Return (flagged_count, true_positives, false_positives) using
    the synthetic ground-truth labels. Ground truth exists only
    because the data is synthetic; a production readout would report
    the flagged count alone."""
    flagged = tp = fp = 0
    for r in rows:
        if r["flagged"]:
            flagged += 1
            if r["true_type"] == "abusive":
                tp += 1
            else:
                fp += 1
    return flagged, tp, fp
