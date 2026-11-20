# enforcement-holdout-eval-kit

**A randomised enforcement holdout that replaces the trust-and-safety headline "we actioned N abusive accounts" with the causal number: how much abuse enforcement actually prevented, measured against flagged accounts deliberately left unenforced — with a friction guardrail gate that refuses rollout when legitimate users pay too much, or when the pilot is too small to prove they don't.**

Every enforcement programme reports actions taken. Almost none of that number is prevented abuse: some flagged actors would have gone dormant on their own and caused no further harm, so counting their actioning as prevention credits enforcement for an outcome that would have happened anyway. The only way to separate the two is a **holdout** — a randomised slice of flagged accounts that are *not* actioned, whose subsequent harm stays observable. This kit builds that measurement end to end: a seeded synthetic account stream with the dormancy planted in, a frozen classifier, the holdout estimator, the friction gate, and the sizing table that prices the holdout itself.

> **Synthetic data only.** Every figure is fabricated by a seeded generator for a fictional social platform (**Fernline**). No real platform, account, or abuse data is used anywhere in this project.

Stdlib-only Python — deliberately. A measurement a launch review relies on is an audit artifact: anyone should be able to read every line of the statistics, re-run it offline, and get byte-identical outputs. Zero network, zero API keys, zero external dependencies. There is deliberately **no threshold tuning here** (the classifier is frozen; tuning a detection rule is a different job), **no review-queue simulation**, and **no SRM or peeking checks** — experiment hygiene of that kind lives in the sibling build [ab-test-integrity-kit](../ab-test-integrity-kit), and rebuilding it here would blur what this kit is about.

## Quickstart

```bash
# 1. Generate a synthetic stream (10,000 accounts, seed 42).
#    --scenario: clean | high_friction | wide_ci
python3 cli.py generate --scenario clean --out dataset.jsonl

# 2. Holdout estimate + friction gate for a stream (file or scenario)
python3 cli.py estimate --input dataset.jsonl
python3 cli.py estimate --scenario high_friction

# 3. Sizing table: CI width vs holdout fraction, with the cost side
python3 cli.py sizing --scenario clean

# 4. Full report: classifier, estimate, sizing, all scenario gates
python3 cli.py report

# 5. CI gate: exit 0 = PASS, 1 = REFUSE, 2 = data-quality / IO error.
#    The seeded high_friction scenario exits 1 BY DESIGN — the gate
#    doing its job looks like a failing check, and the output says why.
python3 cli.py check --input dataset.jsonl
python3 cli.py check --scenario high_friction

# 6. One-command end-to-end demo (incl. localhost serve round-trip)
python3 demo.py

# 7. Tiny localhost API: POST /estimate, GET /report, GET /health
python3 cli.py serve --port 8765
```

## The headline: actions are not prevention

The generator plants the structure that makes the naive number wrong. Of the abusive accounts the classifier flags, a share — planted at **0.40** — are **would-have-churned** actors: they go dormant and cause no further harm even if nobody actions them. Persistent abusive actors cause subsequent harm (1 actor-level harm outcome, 1–3 harm events) if left unenforced, and none once actioned. Because the data is synthetic, the true prevented count is known exactly, so the estimator can be graded against it rather than merely asserted.

On the seeded clean stream (10,000 accounts, 973 flagged, holdout 10%):

| Figure | Value |
|---|---|
| Flagged accounts (true positives / false positives) | 973 (779 / 194) |
| Actioned in the enforcement arm | 887 |
| **Naive prevented** — actioned abusive accounts, each counted as prevented abuse | **710** |
| **Holdout causal prevented** — harm-rate difference between flagged arms, scaled to the enforcement cohort | **422.87** (95% CI 329.24 – 516.50) |
| Ground-truth prevented (known only because the data is synthetic) | 430 |
| Overstatement | 287.13 — **40.4% of the naive figure** |
| Planted would-have-churned share among flagged abusive | 0.395 |

The causal interval covers the ground truth (430) and excludes the naive figure (710) entirely. The overstatement share (0.404) lands on the planted churn share (0.395) — that agreement is the kit's central golden eval (E3/E4), not a coincidence of presentation: an estimator that could not recover the planted share would fail its own evals.

The estimator itself needs no ground truth. It differences the observed harm rate among flagged accounts in the holdout arm (86 accounts, harm observable because nobody actioned them) against the enforcement arm (887 flagged, actioned, no observed harm), and scales the difference back to the enforcement cohort. The false positives dilute the per-flagged rate and inflate the cohort by the same factor, so the two cancel — the estimable number and the true number are the same number, up to the sampling error the interval reports.

## Friction and the guardrail gate

Prevention is only half the readout. On the **same split**, the kit measures **friction**: the false-action rate on legitimate users — classifier false positives who actually get actioned in the enforcement arm (177 of 8,115 legitimate enforcement-arm accounts in the clean stream, 0.0218). A **guardrail metric** is a metric that must not get worse; the gate holds it to a **ceiling declared before the readout** (0.04 — four legitimate users in a hundred) and refuses rollout when:

1. **The friction point estimate exceeds the ceiling** — the measured cost to legitimate users is already over the line, or
2. **The point estimate is under the ceiling but the interval's upper bound is not** — the sample is too small to *show* friction clears the ceiling. "Probably fine" is not clearance.

Prevention is printed next to the verdict and never consulted by it: a gate that strong prevention can override is a dashboard, not a guardrail.

Seeded verdicts:

| Scenario | Friction (95% CI) | Causal prevented | Gate |
|---|---|---|---|
| `clean` — standard population | 0.0218 (upper 0.0250) | 422.87 | **PASS** |
| `high_friction` — a legitimate cohort that looks risky (score mean 0.35 → 0.50); the frozen classifier is unchanged, the population moved | 0.1560 (upper 0.1639) | 385.79 | **REFUSE** — point over ceiling |
| `wide_ci` — clean population, tiny pilot (240 accounts, 50% held out) | 0.0174 (upper 0.0413) | — (too small to read) | **REFUSE** — interval too wide to clear the ceiling |

## The frozen classifier

One ruleset, versioned `v1-frozen`, shared by every scenario and eval: an account is flagged when its risk score is at least **0.65**. Nothing in this kit searches, sweeps, or adjusts that threshold — the measurement team inherits the detection team's classifier as given, which is exactly the situation this kit models. On the clean population it lands at recall 0.792 and a legitimate false-positive rate of 0.0215; the high-friction scenario shows what happens to friction when the *population* drifts under a frozen rule, which is a measurement finding, not a tuning prompt.

## Sizing the holdout

A holdout is not free: every flagged account held out is an abusive account deliberately left unenforced. The sizing table prices both sides at the stream's pooled unenforced harm rate (0.484 per flagged account), using normal-approximation planning widths:

| Holdout fraction | Flagged held out | CI width (per flagged) | CI width (prevented total) | Expected harm left unenforced |
|---|---|---|---|---|
| 1% | 10 | 0.6227 | 599.65 | 4.84 |
| 5% | 49 | 0.2872 | 265.35 | 23.72 |
| 10% | 97 | 0.2096 | 183.63 | 46.95 |
| 25% | 243 | 0.1451 | 105.91 | 117.63 |
| 50% | 486 | 0.1256 | 61.17 | 235.26 |

At 1% the interval is wider than the effect it is trying to measure — an undecidable readout bought cheaply. At 50% the interval is tight and roughly 235 harm-actors' worth of abuse was knowingly let through to buy it. There is no free precision; there is only a chosen point on this table, chosen before the readout, not after it.

## Architecture

| Module | Job |
|---|---|
| `classifier.py` | The frozen ruleset (`v1-frozen`, score ≥ 0.65) — no tuning surface anywhere |
| `generator.py` | Deterministic synthetic Fernline stream (seed 42); planted prevalence 0.10, churn share 0.40, potential harm outcomes per actor; `clean` / `high_friction` / `wide_ci` scenarios; JSONL / CSV / JSON IO |
| `statsmath.py` | Normal quantiles via `statistics.NormalDist`; Wald intervals for a proportion and for a difference of proportions |
| `holdout.py` | The estimator: flagged-cohort harm-rate difference → causal prevented total with CI; naive count and overstatement; friction on the same split; ground-truth truth-check fields (synthetic only) |
| `gate.py` | The guardrail gate: pre-declared friction ceiling, refusal on point estimate or on interval width → PASS / REFUSE |
| `sizing.py` | Planning table: CI width vs holdout fraction at the pooled harm rate, with expected harm left unenforced per row |
| `validation.py` | Data-quality gate: required fields, types, arm/type vocabularies, harm consistency (actioned ⇒ no observed harm), unique accounts — reports issues, never raises |
| `report.py` | Full report assembly: classifier summary, clean readout, sizing table, all three scenario gates |
| `cli.py` | `generate` / `estimate` / `sizing` / `report` / `check` (CI exit 0/1/2) / `demo` / `serve` (stdlib `http.server` on 127.0.0.1: `POST /estimate`, `GET /report`, `GET /health`) |
| `demo.py` | End-to-end narrative with asserts: determinism, the naive-vs-causal gap, all three gate verdicts, sizing monotonicity, check exit codes, live localhost serve round-trip |
| `fixtures/` | The seeded clean stream (`sample_stream.jsonl` + `.csv`) with pinned totals |

## Evals

`python3 evals/run_evals.py` → **12/12 golden evals**, report committed at `evals/eval_report.json` (md5 `79d435f85ea7d49e928ef96c3edef4a3`, byte-identical across 3 verified runs):

- **E1** generator determinism — seed 42 JSONL bytes pinned by md5, 10,000 accounts
- **E2** frozen ruleset — threshold boundary (0.65 flags, 0.6499 does not) and seeded recall / false-positive rate pinned
- **E3** the headline gap — naive 710 vs causal 422.87; overstatement share 0.404406 within 0.08 of the planted churn share 0.395379
- **E4** the causal interval [329.24, 516.50] covers the ground-truth 430 and excludes the naive 710
- **E5** clean friction pinned (0.021811, CI high 0.024989) and the gate passes
- **E6** high-friction refusal pinned — friction 0.156007, refused on the point estimate
- **E7** wide-CI refusal pinned — point 0.017391 under the ceiling, upper bound 0.041283 over it, refused on width alone
- **E8** sizing widths pinned exactly and strictly decreasing; expected harm left unenforced strictly increasing
- **E9** Wald intervals against hand-computed cases
- **E10** CLI `check` exit codes 0 / 1 / 1 / 2 (clean / high-friction / wide-CI / missing file)
- **E11** serve round-trip matches local computation exactly
- **E12** bundled fixture pinned (10,000 rows, 347 observed harm events, validates clean, gate PASS) and the full report deterministic

Unit tests: `python3 -m unittest discover -s tests` → **70 hermetic tests**, including a no-network enforcement test (sockets stubbed), hand-built estimator cases (a 50% holdout harm rate reproduces naive/causal/overstatement exactly), the churn-share extremes (0% churn → no overstatement; 100% churn → the naive figure is entirely overstatement), gate boundary behaviour, sizing monotonicity, validation defects, CLI exit codes, and serve round-trips.

## How this would be used in an integrity programme

The detection team ships a ruleset; before it rolls out platform-wide, the measurement team freezes it and runs it in shadow against a randomised holdout — a small, pre-declared fraction of flagged accounts are not actioned, for a bounded window, under a harm budget the sizing table makes explicit. The readout that goes to the launch review is not "accounts actioned" but the holdout difference with its interval, next to the friction rate with its interval, judged by a gate whose ceiling was agreed before anyone saw the numbers. If the gate refuses on width, the answer is a bigger pilot, not a lower ceiling. If it refuses on friction, the ruleset goes back to the detection team with the false-action count attached — and the prevention estimate, however strong, does not argue back. That separation — detection owns the rule, measurement owns the causal claim, the gate owns the launch — is what keeps an integrity programme's headline number honest quarter after quarter.

## Scope and honest limits

- **The classifier is a scripted stand-in.** One score, one frozen threshold, per-type normal score distributions. A real integration would feed the stream from a production detector's actual flags; the estimator, gate, and sizing table would not change, because none of them look inside the classifier.
- **The harm model is deliberately simple.** Enforcement stops all subsequent harm from an actioned actor, harm is a binary per-actor outcome (with a 1–3 event count carried alongside), and nothing models partial enforcement, appeals, reinstatement, or bad actors returning on new accounts. Each simplification flatters enforcement in a known direction, which is why the kit reports the causal estimate against a *planted* truth instead of claiming realism.
- **Intervals are Wald (normal-approximation).** At the tiny wide-CI pilot's scale the per-flagged difference interval can exceed the [−1, 1] range a difference of proportions must live in — visible in that scenario's own readout, and part of why its gate refuses on width rather than trusting the point estimate. A production version would use a bounded interval (Wilson / Newcombe) for small samples.
- **Friction is one rate.** Real legitimate-user cost includes appeal burden, time-to-restore, and downstream churn of wrongly actioned users; this kit measures the false-action rate only, and the ceiling governs that rate only.
- **The holdout itself has an ethics line the code cannot draw.** Holding out enforcement means knowingly leaving some abuse unenforced for the window; the sizing table quantifies that cost in expected harm so the decision is explicit, but whether the trade is acceptable is a policy call, not a statistical one.
- **The API is a demo surface.** It binds 127.0.0.1 only, holds its stream in memory, and resets on restart.

## Why this project

Integrity and trust-and-safety data roles (the OpenAI Data Scientist, Integrity posting this build is grounded in, 2026-11-20) ask for exactly this shape of work: evaluating detection rules and enforcement controls with randomised holdouts, and balancing abuse prevented against legitimate-user friction with guardrail metrics rather than vibes. This project rebuilds that discipline as a small, inspectable analytics-engineering artifact — the causal claim separated from the action count by an experiment, the friction cost gated by a ceiling declared in advance, and every headline number pinned by a golden eval against a planted ground truth.
