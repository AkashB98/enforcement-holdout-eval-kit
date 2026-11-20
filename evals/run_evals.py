"""Golden evals for enforcement-holdout-eval-kit.

SYNTHETIC DATA ONLY (fictional Fernline stream). Every eval is
deterministic: run_evals.py writes eval_report.json and the file
must be byte-identical across runs. No timestamps, ports, or temp
paths enter the report - only names, booleans, and pinned numbers.

E1-E2 pin the generator and the frozen classifier. E3-E4 are the
headline: the naive count overstates prevented abuse by roughly the
planted would-have-churned share, and the holdout interval covers
the ground truth while excluding the naive figure. E5-E7 pin the
guardrail gate (clean passes; high friction refused on its point
estimate; the tiny pilot refused on interval width alone). E8 pins
the sizing trade-off. E9-E12 pin the statistics primitives, the CLI
exit codes, the serve round-trip, and the bundled fixture.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import threading
import urllib.request
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import FLAG_THRESHOLD, is_flagged  # noqa: E402
from cli import EXIT_ERROR, EXIT_FAIL, EXIT_OK, main as cli_main  # noqa: E402
from cli import make_server, reset_state
from gate import evaluate_stream  # noqa: E402
from generator import generate_scenario, load_rows, rows_to_jsonl  # noqa: E402
from report import build_report  # noqa: E402
from sizing import sizing_table  # noqa: E402
from statsmath import difference_ci, proportion_ci  # noqa: E402
from validation import validate_dataset  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(ROOT, "fixtures", "sample_stream.jsonl")
RESULTS = []


def check(name, passed, detail=""):
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return passed


def _run_cli(argv):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return cli_main(argv)


def main():
    print("== golden evals: enforcement-holdout-eval-kit ==")
    clean = generate_scenario("clean")
    clean_est = evaluate_stream(clean)

    # E1: generator determinism (bytes pinned)
    text1 = rows_to_jsonl(generate_scenario("clean"))
    md5 = hashlib.md5(text1.encode()).hexdigest()
    check("E1 generator determinism (seed=42, 10000 accounts)",
          text1 == rows_to_jsonl(generate_scenario("clean"))
          and len(clean) == 10000
          and md5 == "fb7fb4809828490092450c97f6b13665",
          f"jsonl_md5={md5}")

    # E2: frozen classifier (threshold + seeded recall / FPR pinned)
    clf = build_report()["classifier"]
    check("E2 frozen ruleset v1 (threshold 0.65; recall 0.792472, FPR 0.021515)",
          FLAG_THRESHOLD == 0.65 and is_flagged(0.65)
          and not is_flagged(0.6499)
          and clf["recall"] == 0.792472
          and clf["false_positive_rate"] == 0.021515
          and clf["flagged"] == 973,
          f"recall={clf['recall']} fpr={clf['false_positive_rate']}")

    # E3: the headline gap - naive overstates by ~ the churn share
    est = clean_est["estimate"]
    check("E3 naive 710 vs causal 422.87 (overstatement share 0.404406 ~ churn)",
          est["naive_prevented"] == 710
          and est["causal_prevented"]["total"] == 422.871928
          and est["overstatement_share_of_naive"] == 0.404406
          and abs(est["overstatement_share_of_naive"]
                  - est["churn_share_flagged_abusive"]) <= 0.08
          and abs(est["overstatement_share_of_naive"] - 0.40) <= 0.08,
          f"over_share={est['overstatement_share_of_naive']} "
          f"churn={est['churn_share_flagged_abusive']}")

    # E4: the causal interval covers ground truth, excludes naive
    causal = est["causal_prevented"]
    check("E4 causal CI [329.24, 516.50] covers truth 430, excludes naive 710",
          causal["ci_low"] == 329.240208 and causal["ci_high"] == 516.503648
          and causal["ci_low"] <= est["true_prevented_ground_truth"]
          <= causal["ci_high"]
          and causal["ci_high"] < est["naive_prevented"],
          f"truth={est['true_prevented_ground_truth']}")

    # E5: clean friction pinned, gate passes
    fric = est["friction"]
    check("E5 clean friction 0.021811 (CI high 0.024989 <= 0.04), gate PASS",
          fric["estimate"] == 0.021811 and fric["ci_high"] == 0.024989
          and fric["false_actions"] == 177
          and clean_est["gate"]["verdict"] == "PASS",
          f"friction={fric['estimate']}")

    # E6: high friction refused on the point estimate
    hf = evaluate_stream(generate_scenario("high_friction"))
    check("E6 high-friction gate REFUSE (friction 0.156007, by point)",
          hf["estimate"]["friction"]["estimate"] == 0.156007
          and hf["gate"]["verdict"] == "REFUSE"
          and hf["gate"]["refused_by"] == "friction_exceeds_ceiling",
          f"friction={hf['estimate']['friction']['estimate']}")

    # E7: wide-CI pilot refused on interval width alone
    wc = evaluate_stream(generate_scenario("wide_ci"))
    wf = wc["estimate"]["friction"]
    check("E7 wide-CI gate REFUSE (point 0.017391 <= 0.04 < bound 0.041283)",
          wf["estimate"] == 0.017391 and wf["ci_high"] == 0.041283
          and wf["estimate"] <= 0.04 < wf["ci_high"]
          and wc["gate"]["verdict"] == "REFUSE"
          and wc["gate"]["refused_by"] == "friction_ci_too_wide",
          f"point={wf['estimate']} high={wf['ci_high']}")

    # E8: sizing trade-off pinned (widths fall, harm-through rises)
    table = sizing_table(clean)
    widths = [r["ci_width_per_flagged"] for r in table["rows"]]
    harm = [r["expected_harm_left_unenforced"] for r in table["rows"]]
    check("E8 sizing widths pinned and strictly decreasing",
          widths == [0.622688, 0.287177, 0.209626, 0.145084, 0.125603]
          and all(b < a for a, b in zip(widths, widths[1:]))
          and all(b > a for a, b in zip(harm, harm[1:])),
          f"widths={widths}")

    # E9: statistics primitives, hand-computed
    p = proportion_ci(50, 100)
    d = difference_ci(0, 100, 50, 100)
    check("E9 Wald CIs hand-pinned (prop 0.5 +- 0.098; diff se 0.05)",
          p["estimate"] == 0.5 and abs(p["ci_low"] - 0.402) < 0.001
          and abs(p["ci_high"] - 0.598) < 0.001
          and d["difference"] == 0.5 and d["se"] == 0.05)

    # E10: CLI check exit codes 0 / 1 / 1 / 2
    import tempfile
    tmp = tempfile.mkdtemp(prefix="holdout-evals-")
    clean_path = os.path.join(tmp, "clean.jsonl")
    hf_path = os.path.join(tmp, "hf.jsonl")
    with open(clean_path, "w", encoding="utf-8") as fh:
        fh.write(rows_to_jsonl(clean))
    with open(hf_path, "w", encoding="utf-8") as fh:
        fh.write(rows_to_jsonl(generate_scenario("high_friction")))
    codes = (_run_cli(["check", "--input", clean_path]),
             _run_cli(["check", "--input", hf_path]),
             _run_cli(["check", "--scenario", "wide_ci"]),
             _run_cli(["check", "--input", "/tmp/no-such-holdout-xyz.jsonl"]))
    check("E10 CLI check exit codes 0/1/1/2",
          codes == (EXIT_OK, EXIT_FAIL, EXIT_FAIL, EXIT_ERROR),
          f"codes={codes}")

    # E11: serve round-trip matches local computation
    reset_state(clean)
    server = make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/estimate", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            served = json.loads(resp.read())
        serve_ok = served == clean_est
    finally:
        server.shutdown()
        server.server_close()
        reset_state()
    check("E11 serve round-trip matches local estimate", serve_ok)

    # E12: fixture pinned + full report deterministic
    fixture = load_rows(FIXTURE)
    total_events = sum(r["harm_events_observed"] for r in fixture)
    rep1, rep2 = build_report(), build_report()
    check("E12 fixture pinned (10000 rows, 347 harm events) + report stable",
          len(fixture) == 10000 and total_events == 347
          and validate_dataset(fixture) == []
          and evaluate_stream(fixture)["gate"]["verdict"] == "PASS"
          and rep1 == rep2,
          f"total_harm_events={total_events}")

    passed = sum(1 for r in RESULTS if r["passed"])
    total_n = len(RESULTS)
    summary_doc = {"passed": passed, "total": total_n,
                   "all_passed": passed == total_n, "evals": RESULTS}
    with open(os.path.join(HERE, "eval_report.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary_doc, sort_keys=True) + "\n")
    print(f"\n{passed}/{total_n} evals passed -> evals/eval_report.json")
    return 0 if passed == total_n else 1


if __name__ == "__main__":
    sys.exit(main())
