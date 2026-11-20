"""Full report assembly: classifier summary, the holdout estimate,
friction, the gate, the sizing table, and the gate's verdict on all
three planted scenarios — one document."""

from __future__ import annotations

from typing import Dict, List, Sequence

from classifier import RULESET_VERSION, classify_rows
from gate import evaluate_stream
from generator import generate_scenario
from sizing import sizing_table


def _classifier_summary(rows: Sequence[Dict]) -> Dict:
    flagged, tp, fp = classify_rows(rows)
    abusive = sum(1 for r in rows if r["true_type"] == "abusive")
    legit = len(rows) - abusive
    fn = abusive - tp
    return {
        "ruleset_version": RULESET_VERSION,
        "accounts": len(rows),
        "abusive_ground_truth": abusive,
        "legitimate_ground_truth": legit,
        "flagged": flagged,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "recall": round(tp / abusive, 6) if abusive else 0.0,
        "false_positive_rate": round(fp / legit, 6) if legit else 0.0,
        "precision": round(tp / flagged, 6) if flagged else 0.0,
    }


def build_report(rows: Sequence[Dict] | None = None) -> Dict:
    clean = list(rows) if rows is not None else generate_scenario("clean")
    scenarios = {}
    for name in ("clean", "high_friction", "wide_ci"):
        scen_rows = clean if (rows is not None and name == "clean") \
            else generate_scenario(name)
        scenarios[name] = evaluate_stream(scen_rows)
    return {
        "dataset": {
            "rows": len(clean),
            "synthetic": True,
            "platform": "Fernline (fictional)",
        },
        "classifier": _classifier_summary(clean),
        "clean": evaluate_stream(clean),
        "sizing": sizing_table(clean),
        "scenarios": scenarios,
    }
