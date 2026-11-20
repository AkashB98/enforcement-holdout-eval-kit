"""Data-quality gate: reports issues, never raises.

Checks the fields the estimator and gate rely on: required fields
present, types sane (including the bool-is-an-int trap in reverse —
harm fields must be genuine 0/1 ints, flag fields genuine bools),
risk scores in range, arms and types from the known vocabularies,
harm fields internally consistent (observed harm is the unenforced
outcome unless the account was actioned), and account ids unique.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from generator import ROW_FIELDS

_ARMS = ("enforcement", "holdout")
_TYPES = ("abusive", "legitimate")


def validate_dataset(rows: Sequence[Dict]) -> List[str]:
    issues: List[str] = []
    if not rows:
        return ["dataset is empty"]
    seen = set()
    for i, r in enumerate(rows):
        where = f"row {i + 1}"
        if not isinstance(r, dict):
            issues.append(f"{where}: not an object")
            continue
        missing = [f for f in ROW_FIELDS if f not in r]
        if missing:
            issues.append(f"{where}: missing fields {missing}")
            continue
        if r["account_id"] in seen:
            issues.append(f"{where}: duplicate account_id {r['account_id']}")
        seen.add(r["account_id"])
        if r["true_type"] not in _TYPES:
            issues.append(f"{where}: unknown true_type {r['true_type']!r}")
        if r["arm"] not in _ARMS:
            issues.append(f"{where}: unknown arm {r['arm']!r}")
        if not isinstance(r["risk_score"], (int, float)) \
                or isinstance(r["risk_score"], bool) \
                or not 0.0 <= r["risk_score"] <= 1.0:
            issues.append(f"{where}: risk_score out of range: {r['risk_score']!r}")
        for f in ("flagged", "would_churn", "actioned"):
            if not isinstance(r[f], bool):
                issues.append(f"{where}: {f} must be a bool, got {r[f]!r}")
        for f in ("harm_if_unenforced", "harm_events_if_unenforced",
                  "harm_observed", "harm_events_observed"):
            if not isinstance(r[f], int) or isinstance(r[f], bool) \
                    or r[f] < 0:
                issues.append(f"{where}: {f} must be a non-negative int")
        if isinstance(r.get("harm_if_unenforced"), int) \
                and r["harm_if_unenforced"] not in (0, 1):
            issues.append(f"{where}: harm_if_unenforced must be 0 or 1")
        if r.get("actioned") is True and r.get("harm_observed") not in (0, None):
            if r["harm_observed"] != 0:
                issues.append(f"{where}: actioned account shows observed harm")
        if r.get("actioned") is False \
                and r.get("harm_observed") != r.get("harm_if_unenforced"):
            issues.append(f"{where}: unactioned harm_observed != harm_if_unenforced")
        if len(issues) > 50:
            issues.append("... (truncated)")
            break
    arms = {r["arm"] for r in rows if isinstance(r, dict) and "arm" in r}
    if len(arms) < 2:
        issues.append("dataset must contain both arms")
    return issues
