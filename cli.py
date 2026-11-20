"""CLI: generate | estimate | sizing | report | check | demo | serve.

SYNTHETIC DATA ONLY - Fernline is a fictional platform and every
dataset handled here is fabricated sample data.

Exit codes:
  check : 0 = gate PASS, 1 = gate REFUSE (friction over the ceiling,
          or its interval too wide to clear it — the seeded
          high_friction scenario exits 1 BY DESIGN),
          2 = usage / IO / data-quality error
  others: 0 = success, 2 = usage / IO error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate import DEFAULT_FRICTION_CEILING, evaluate_stream  # noqa: E402
from generator import (DEFAULT_SEED, SCENARIOS, generate_scenario,  # noqa: E402
                       load_rows, write_rows)
from report import build_report  # noqa: E402
from sizing import sizing_table  # noqa: E402
from validation import validate_dataset  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_ERROR = 0, 1, 2


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def _load_or_error(path: str) -> Optional[List[Dict]]:
    try:
        return load_rows(path)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
    except (ValueError, OSError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
    return None


def _rows_or_error(args):
    """Rows from --input, or from --scenario when no input is given."""
    if getattr(args, "input", None):
        rows = _load_or_error(args.input)
        if rows is None:
            return None, EXIT_ERROR
        issues = validate_dataset(rows)
        if issues:
            for issue in issues[:20]:
                print(f"data-quality: {issue}", file=sys.stderr)
            return None, EXIT_ERROR
        return rows, EXIT_OK
    scenario = getattr(args, "scenario", "clean")
    return generate_scenario(scenario, seed=getattr(args, "seed", DEFAULT_SEED)), EXIT_OK


def _write_out(args, text: str, summary: str) -> int:
    if getattr(args, "out", None):
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(summary)
    else:
        print(text, end="")
    return EXIT_OK


def cmd_generate(args) -> int:
    rows = generate_scenario(args.scenario, seed=args.seed,
                             n_accounts=args.n_accounts)
    fmt = "csv" if (args.out and args.out.endswith(".csv")) else "jsonl"
    if args.out:
        try:
            write_rows(rows, args.out, fmt=fmt)
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(f"generated {len(rows)} synthetic rows "
              f"(scenario={args.scenario}, seed={args.seed}) -> {args.out}")
        return EXIT_OK
    from generator import rows_to_csv, rows_to_jsonl
    print(rows_to_csv(rows) if fmt == "csv" else rows_to_jsonl(rows), end="")
    return EXIT_OK


def cmd_estimate(args) -> int:
    rows, code = _rows_or_error(args)
    if rows is None:
        return code
    try:
        result = evaluate_stream(rows, ceiling=args.ceiling)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return _write_out(args, canonical(result) + "\n", f"estimate -> {args.out}")


def cmd_sizing(args) -> int:
    rows, code = _rows_or_error(args)
    if rows is None:
        return code
    try:
        result = sizing_table(rows)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return _write_out(args, canonical(result) + "\n", f"sizing -> {args.out}")


def cmd_report(args) -> int:
    rows = None
    if args.input:
        rows, code = _rows_or_error(args)
        if rows is None:
            return code
    report = build_report(rows)
    return _write_out(args, canonical(report) + "\n", f"report -> {args.out}")


def cmd_check(args) -> int:
    if args.input:
        rows = _load_or_error(args.input)
        if rows is None:
            return EXIT_ERROR
        issues = validate_dataset(rows)
        if issues:
            for issue in issues[:20]:
                print(f"data-quality: {issue}")
            print(f"check FAIL (data quality): {len(issues)} issue(s)")
            return EXIT_ERROR
    else:
        rows = generate_scenario(args.scenario, seed=args.seed)
    try:
        result = evaluate_stream(rows, ceiling=args.ceiling)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    est, gate = result["estimate"], result["gate"]
    print(f"verdict={gate['verdict']} refused_by={gate['refused_by']} "
          f"naive_prevented={est['naive_prevented']} "
          f"causal_prevented={est['causal_prevented']['total']} "
          f"friction={est['friction']['estimate']} "
          f"friction_ci_high={est['friction']['ci_high']} "
          f"ceiling={gate['friction_ceiling']}")
    if gate["verdict"] == "REFUSE":
        for reason in gate["refusal_reasons"]:
            print(f"refusal: {reason}")
        print("check FAIL (gate refused rollout)")
        return EXIT_FAIL
    print("check PASS")
    return EXIT_OK


def cmd_demo(args) -> int:
    import demo as demo_mod
    try:
        demo_mod.main()
    except AssertionError as exc:
        print(f"demo FAILED: {exc}", file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


# ------------------------------------------------------------------- serve

class _State:
    def __init__(self):
        self.rows: List[Dict] = generate_scenario("clean")


_STATE = _State()


def get_state() -> _State:
    return _STATE


def reset_state(rows: Optional[List[Dict]] = None) -> None:
    _STATE.rows = list(rows) if rows is not None else generate_scenario("clean")


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: Any) -> None:
        body = (canonical(payload) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            return self._send_json(200, {"status": "ok"})
        if self.path == "/report":
            try:
                return self._send_json(200, build_report(_STATE.rows))
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})
        return self._send_json(404, {"error": "unknown endpoint"})

    def do_POST(self):  # noqa: N802
        if self.path != "/estimate":
            return self._send_json(404, {"error": "unknown endpoint"})
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw) if raw.strip() else {}
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
            rows = body.get("rows", _STATE.rows)
            ceiling = float(body.get("ceiling", DEFAULT_FRICTION_CEILING))
            return self._send_json(200, evaluate_stream(rows, ceiling=ceiling))
        except (ValueError, TypeError, KeyError) as exc:
            return self._send_json(400, {"error": f"bad request: {exc}"})

    def log_message(self, *a: Any) -> None:
        pass


def make_server(port: int) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), _Handler)


def cmd_serve(args) -> int:
    if args.input:
        rows = _load_or_error(args.input)
        if rows is None:
            return EXIT_ERROR
        reset_state(rows)
    server = make_server(args.port)
    print(f"serving on http://127.0.0.1:{args.port}  "
          f"(POST /estimate, GET /report, GET /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="enforcement-holdout-eval-kit",
        description="Randomised enforcement-holdout evaluator (Fernline sample data).")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate a synthetic account stream")
    g.add_argument("--scenario", choices=SCENARIOS, default="clean")
    g.add_argument("--seed", type=int, default=DEFAULT_SEED)
    g.add_argument("--n-accounts", type=int, default=None)
    g.add_argument("--out", default=None)
    g.set_defaults(func=cmd_generate)

    for name, fn, helptext in (
            ("estimate", cmd_estimate, "holdout estimate + gate for a stream"),
            ("sizing", cmd_sizing, "CI width vs holdout fraction table"),
            ("report", cmd_report, "full report, one document")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--input", default=None)
        sp.add_argument("--scenario", choices=SCENARIOS, default="clean")
        sp.add_argument("--seed", type=int, default=DEFAULT_SEED)
        sp.add_argument("--out", default=None)
        if name == "estimate":
            sp.add_argument("--ceiling", type=float,
                            default=DEFAULT_FRICTION_CEILING)
        sp.set_defaults(func=fn)

    c = sub.add_parser("check", help="CI gate: exit 0 pass / 1 refusal / 2 error")
    c.add_argument("--input", default=None)
    c.add_argument("--scenario", choices=SCENARIOS, default="clean")
    c.add_argument("--seed", type=int, default=DEFAULT_SEED)
    c.add_argument("--ceiling", type=float, default=DEFAULT_FRICTION_CEILING)
    c.set_defaults(func=cmd_check)

    sub.add_parser("demo", help="run the end-to-end demo").set_defaults(func=cmd_demo)

    sv = sub.add_parser("serve", help="localhost JSON API")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--input", default=None)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
