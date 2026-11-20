"""Deterministic synthetic account stream — Fernline (fictional).

SYNTHETIC DATA ONLY. No real platform, account, or abuse data is ever
used. Every row is fabricated from a seeded PRNG so the same seed
always yields the same stream, byte-for-byte.

One row per account:

  account_id, true_type, risk_score, flagged, would_churn, arm,
  actioned, harm_if_unenforced, harm_events_if_unenforced,
  harm_observed, harm_events_observed

- ``true_type`` — ground truth: ``abusive`` with planted prevalence
  0.10, else ``legitimate``. Only a synthetic generator can know
  this; it is what makes the causal effect checkable.
- ``risk_score`` — drawn from a per-type normal (abusive mean 0.78,
  legitimate mean 0.35 in the clean scenario), clipped to [0, 1].
  The frozen classifier in ``classifier.py`` flags score >= 0.65,
  which lands recall near 0.81 and a legitimate false-positive rate
  near 0.023 by construction.
- ``would_churn`` — the plant the whole kit turns on. A share
  (0.40) of abusive actors are *would-have-churned*: even if nobody
  enforces against them, they go dormant and cause no further harm.
  The naive headline counts them as prevented abuse anyway.
- ``harm_if_unenforced`` / ``harm_events_if_unenforced`` — the
  potential outcome with no enforcement: 1 (and 1-3 events) for a
  persistent abusive actor, 0 for a would-have-churned actor and
  for every legitimate account.
- ``arm`` — the randomised holdout assignment: ``enforcement``
  (flagged actors are actioned) or ``holdout`` (flagged actors are
  deliberately NOT actioned, so their harm stays observable).
- ``actioned`` — flagged and in the enforcement arm.
- ``harm_observed`` — 0 for an actioned actor (enforcement stops
  the subsequent harm in this model), else the unenforced outcome.

Scenarios plant the situations the gate exists to judge:

- ``clean``         — the standard population; friction clears the
                      pre-declared ceiling and the gate passes.
- ``high_friction`` — a legitimate cohort that *looks* risky (its
                      score mean shifts to 0.50). The classifier is
                      unchanged — the population moved — so the same
                      frozen ruleset actions far more legitimate
                      users and the gate must refuse on friction.
- ``wide_ci``       — the clean population, but a tiny pilot
                      (240 accounts, 50% held out): the friction
                      point estimate sits under the ceiling while
                      its interval is far too wide to clear it, and
                      the gate must refuse on uncertainty.
"""

from __future__ import annotations

import csv
import io
import json
import random
from typing import Dict, List, Sequence

from classifier import FLAG_THRESHOLD

DEFAULT_SEED = 42
DEFAULT_N_ACCOUNTS = 10000
ABUSE_PREVALENCE = 0.10
CHURN_SHARE = 0.40
ABUSIVE_SCORE_MEAN = 0.78
LEGIT_SCORE_MEAN = 0.35
LEGIT_SCORE_MEAN_HIGH_FRICTION = 0.50
SCORE_SD = 0.15
DEFAULT_HOLDOUT_FRACTION = 0.10

ROW_FIELDS = ["account_id", "true_type", "risk_score", "flagged",
              "would_churn", "arm", "actioned", "harm_if_unenforced",
              "harm_events_if_unenforced", "harm_observed",
              "harm_events_observed"]

SCENARIOS = ("clean", "high_friction", "wide_ci")

_BOOL_FIELDS = ("flagged", "would_churn", "actioned")
_INT_FIELDS = ("harm_if_unenforced", "harm_events_if_unenforced",
               "harm_observed", "harm_events_observed")


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def generate_stream(seed: int = DEFAULT_SEED,
                    n_accounts: int = DEFAULT_N_ACCOUNTS,
                    abuse_prevalence: float = ABUSE_PREVALENCE,
                    churn_share: float = CHURN_SHARE,
                    abusive_mean: float = ABUSIVE_SCORE_MEAN,
                    legit_mean: float = LEGIT_SCORE_MEAN,
                    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION
                    ) -> List[Dict]:
    """Return synthetic per-account rows, deterministic for ``seed``."""
    if n_accounts < 20:
        raise ValueError("n_accounts must be >= 20")
    if not 0.0 < abuse_prevalence < 1.0:
        raise ValueError("abuse_prevalence must be in (0, 1)")
    if not 0.0 <= churn_share <= 1.0:
        raise ValueError("churn_share must be in [0, 1]")
    if not 0.0 < holdout_fraction < 1.0:
        raise ValueError("holdout_fraction must be in (0, 1)")

    rng = random.Random(seed)
    rows: List[Dict] = []
    for i in range(n_accounts):
        abusive = rng.random() < abuse_prevalence
        mean = abusive_mean if abusive else legit_mean
        score = round(_clip01(rng.gauss(mean, SCORE_SD)), 4)
        flagged = score >= FLAG_THRESHOLD
        churn = bool(abusive and rng.random() < churn_share)
        if abusive and not churn:
            harm, events = 1, rng.randint(1, 3)
        else:
            harm, events = 0, 0
        arm = "holdout" if rng.random() < holdout_fraction else "enforcement"
        actioned = bool(flagged and arm == "enforcement")
        rows.append({
            "account_id": f"acct_{i + 1:05d}",
            "true_type": "abusive" if abusive else "legitimate",
            "risk_score": score,
            "flagged": flagged,
            "would_churn": churn,
            "arm": arm,
            "actioned": actioned,
            "harm_if_unenforced": harm,
            "harm_events_if_unenforced": events,
            "harm_observed": 0 if actioned else harm,
            "harm_events_observed": 0 if actioned else events,
        })
    return rows


def generate_scenario(scenario: str = "clean", seed: int = DEFAULT_SEED,
                      n_accounts: int | None = None) -> List[Dict]:
    """Generate one of the named planted scenarios (see docstring)."""
    if scenario == "clean":
        return generate_stream(seed=seed, n_accounts=n_accounts or DEFAULT_N_ACCOUNTS)
    if scenario == "high_friction":
        return generate_stream(seed=seed,
                               n_accounts=n_accounts or DEFAULT_N_ACCOUNTS,
                               legit_mean=LEGIT_SCORE_MEAN_HIGH_FRICTION)
    if scenario == "wide_ci":
        return generate_stream(seed=seed, n_accounts=n_accounts or 240,
                               holdout_fraction=0.50)
    raise ValueError(f"unknown scenario: {scenario!r} (choose from {SCENARIOS})")


def arm_counts(rows: Sequence[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["arm"]] = counts.get(r["arm"], 0) + 1
    return counts


def rows_to_jsonl(rows: Sequence[Dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def rows_to_csv(rows: Sequence[Dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ROW_FIELDS)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value in ("True", "true", "1"):
            return True
        if value in ("False", "false", "0"):
            return False
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"not a boolean: {value!r}")


def _coerce_row(raw: Dict, lineno: int) -> Dict:
    try:
        row = {
            "account_id": str(raw["account_id"]),
            "true_type": str(raw["true_type"]),
            "risk_score": float(raw["risk_score"]),
            "arm": str(raw["arm"]),
        }
        for f in _BOOL_FIELDS:
            row[f] = _as_bool(raw[f])
        for f in _INT_FIELDS:
            row[f] = int(raw[f])
        return {f: row[f] for f in ROW_FIELDS}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"line {lineno}: bad row {raw!r}: {exc}") from exc


def load_rows(path: str) -> List[Dict]:
    """Load rows from .jsonl, .csv, or a JSON array file."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        return [_coerce_row(r, i + 2) for i, r in enumerate(reader)]
    stripped = text.strip()
    if stripped.startswith("["):
        data = json.loads(stripped)
        if not isinstance(data, list):
            raise ValueError("JSON input must be an array of rows")
        return [_coerce_row(r, i + 1) for i, r in enumerate(data)]
    rows = []
    for i, line in enumerate(text.splitlines()):
        if line.strip():
            rows.append(_coerce_row(json.loads(line), i + 1))
    return rows


def write_rows(rows: Sequence[Dict], path: str, fmt: str = "jsonl") -> None:
    text = rows_to_csv(rows) if fmt == "csv" else rows_to_jsonl(rows)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
