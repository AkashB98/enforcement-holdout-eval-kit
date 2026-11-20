"""End-to-end demo: generate -> frozen classifier -> naive vs causal
-> friction gate (clean passes, high-friction and wide-CI refused)
-> sizing trade-off -> check -> serve.

SYNTHETIC DATA ONLY (fictional Fernline stream). Runs fully offline;
the serve round-trip is loopback-only on an ephemeral port. Every
stage asserts.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import EXIT_OK, main as cli_main, make_server, reset_state  # noqa: E402
from gate import evaluate_stream  # noqa: E402
from generator import generate_scenario, rows_to_jsonl  # noqa: E402
from sizing import sizing_table  # noqa: E402
from validation import validate_dataset  # noqa: E402


def _request(port: int, path: str, payload=None, method: str = "GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def main() -> None:
    print("== 1. generate synthetic Fernline stream (seed=42) ==")
    rows = generate_scenario("clean")
    again = generate_scenario("clean")
    assert rows == again, "generator must be deterministic"
    assert len(rows) == 10000, len(rows)
    assert validate_dataset(rows) == [], validate_dataset(rows)[:3]
    print(f"   {len(rows)} accounts, deterministic, clean")

    print("\n== 2. the headline gap: naive vs holdout causal ==")
    clean = evaluate_stream(rows)
    est = clean["estimate"]
    assert est["naive_prevented"] > est["causal_prevented"]["total"], est
    assert abs(est["overstatement_share_of_naive"] - 0.40) < 0.08, est
    assert est["causal_prevented"]["ci_low"] \
        <= est["true_prevented_ground_truth"] \
        <= est["causal_prevented"]["ci_high"], est
    print(f"   naive={est['naive_prevented']} actioned abusive counted as prevented")
    print(f"   causal={est['causal_prevented']['total']} "
          f"(95% CI {est['causal_prevented']['ci_low']}.."
          f"{est['causal_prevented']['ci_high']}), "
          f"ground truth={est['true_prevented_ground_truth']}")
    print(f"   overstatement share={est['overstatement_share_of_naive']} "
          f"vs planted would-have-churned share="
          f"{est['churn_share_flagged_abusive']}")

    print("\n== 3. friction gate: clean passes at the 0.04 ceiling ==")
    assert clean["gate"]["verdict"] == "PASS", clean["gate"]
    print(f"   friction={est['friction']['estimate']} "
          f"CI high={est['friction']['ci_high']} <= 0.04 -> PASS")

    print("\n== 4. gate refuses high friction (point over ceiling) ==")
    hf = evaluate_stream(generate_scenario("high_friction"))
    assert hf["gate"]["verdict"] == "REFUSE", hf["gate"]
    assert hf["gate"]["refused_by"] == "friction_exceeds_ceiling", hf["gate"]
    print(f"   friction={hf['estimate']['friction']['estimate']} > 0.04 "
          "-> REFUSE (friction_exceeds_ceiling), prevention not consulted")

    print("\n== 5. gate refuses a wide-CI pilot (point under, bound over) ==")
    wc = evaluate_stream(generate_scenario("wide_ci"))
    assert wc["gate"]["verdict"] == "REFUSE", wc["gate"]
    assert wc["gate"]["refused_by"] == "friction_ci_too_wide", wc["gate"]
    assert wc["estimate"]["friction"]["estimate"] <= 0.04
    assert wc["estimate"]["friction"]["ci_high"] > 0.04
    print(f"   friction={wc['estimate']['friction']['estimate']} <= 0.04 but "
          f"CI high={wc['estimate']['friction']['ci_high']} > 0.04 "
          "-> REFUSE (friction_ci_too_wide)")

    print("\n== 6. sizing: wider holdout, narrower interval, more harm through ==")
    table = sizing_table(rows)["rows"]
    widths = [r["ci_width_per_flagged"] for r in table]
    let_through = [r["expected_harm_left_unenforced"] for r in table]
    assert all(b < a for a, b in zip(widths, widths[1:])), widths
    assert all(b > a for a, b in zip(let_through, let_through[1:])), let_through
    for r in table:
        print(f"   holdout {r['holdout_fraction']:.0%}: CI width "
              f"{r['ci_width_per_flagged']}, expected harm unenforced "
              f"{r['expected_harm_left_unenforced']}")

    print("\n== 7. CLI check gate (high_friction exits 1 BY DESIGN) ==")
    import tempfile
    tmp = tempfile.mkdtemp(prefix="holdout-demo-")
    clean_path = os.path.join(tmp, "clean.jsonl")
    hf_path = os.path.join(tmp, "hf.jsonl")
    with open(clean_path, "w", encoding="utf-8") as fh:
        fh.write(rows_to_jsonl(rows))
    with open(hf_path, "w", encoding="utf-8") as fh:
        fh.write(rows_to_jsonl(generate_scenario("high_friction")))
    code_ok = cli_main(["check", "--input", clean_path])
    code_refuse = cli_main(["check", "--input", hf_path])
    code_err = cli_main(["check", "--input", "/tmp/no-such-holdout-xyz.jsonl"])
    print(f"   clean={code_ok} high_friction={code_refuse} missing-file={code_err}")
    assert (code_ok, code_refuse, code_err) == (EXIT_OK, 1, 2)

    print("\n== 8. live localhost serve round-trip ==")
    reset_state(rows)
    server = make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, health = _request(port, "/health")
        assert status == 200 and health == {"status": "ok"}
        status, served = _request(port, "/estimate", payload={}, method="POST")
        assert status == 200 and served == clean, (served, clean)
        status, served_report = _request(port, "/report")
        assert status == 200 and served_report["clean"] == clean
        print("   POST /estimate and GET /report match local computation")
    finally:
        server.shutdown()
        server.server_close()
        reset_state()

    print("\nDemo OK: generate, naive-vs-causal gap, friction gate "
          "(pass + both refusals), sizing, check and serve verified.")


if __name__ == "__main__":
    main()
