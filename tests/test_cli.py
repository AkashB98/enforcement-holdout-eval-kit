import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import EXIT_ERROR, EXIT_FAIL, EXIT_OK, main as cli_main  # noqa: E402
from generator import generate_scenario, rows_to_jsonl  # noqa: E402


def _run(argv):
    with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
        code = cli_main(argv)
    return code, out.getvalue()


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="holdout-cli-")
        self.clean_path = os.path.join(self.tmp, "clean.jsonl")
        self.hf_path = os.path.join(self.tmp, "hf.jsonl")
        with open(self.clean_path, "w", encoding="utf-8") as fh:
            fh.write(rows_to_jsonl(generate_scenario("clean")))
        with open(self.hf_path, "w", encoding="utf-8") as fh:
            fh.write(rows_to_jsonl(generate_scenario("high_friction")))

    def test_check_exit_codes(self):
        self.assertEqual(_run(["check", "--input", self.clean_path])[0], EXIT_OK)
        self.assertEqual(_run(["check", "--input", self.hf_path])[0], EXIT_FAIL)
        self.assertEqual(_run(["check", "--scenario", "wide_ci"])[0], EXIT_FAIL)
        self.assertEqual(
            _run(["check", "--input", "/tmp/no-such-holdout-xyz.jsonl"])[0],
            EXIT_ERROR)

    def test_check_scenario_clean_passes(self):
        code, out = _run(["check", "--scenario", "clean"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("verdict=PASS", out)

    def test_estimate_json_shape(self):
        code, out = _run(["estimate", "--input", self.clean_path])
        self.assertEqual(code, EXIT_OK)
        doc = json.loads(out)
        self.assertIn("causal_prevented", doc["estimate"])
        self.assertEqual(doc["gate"]["verdict"], "PASS")

    def test_generate_to_file(self):
        out_path = os.path.join(self.tmp, "gen.jsonl")
        code, _ = _run(["generate", "--scenario", "wide_ci",
                        "--out", out_path])
        self.assertEqual(code, EXIT_OK)
        with open(out_path, encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().strip().splitlines()), 240)

    def test_sizing_json(self):
        code, out = _run(["sizing", "--scenario", "clean"])
        self.assertEqual(code, EXIT_OK)
        doc = json.loads(out)
        self.assertEqual(len(doc["rows"]), 5)

    def test_report_json(self):
        code, out = _run(["report"])
        self.assertEqual(code, EXIT_OK)
        doc = json.loads(out)
        self.assertEqual(doc["scenarios"]["wide_ci"]["gate"]["refused_by"],
                         "friction_ci_too_wide")

    def test_serve_round_trip(self):
        import threading
        import urllib.request
        from cli import make_server, reset_state
        from gate import evaluate_stream
        rows = generate_scenario("clean")
        reset_state(rows)
        server = make_server(0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=10) as resp:
                self.assertEqual(json.loads(resp.read()), {"status": "ok"})
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/estimate", data=b"{}",
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                served = json.loads(resp.read())
            self.assertEqual(served, evaluate_stream(rows))
        finally:
            server.shutdown()
            server.server_close()
            reset_state()


if __name__ == "__main__":
    unittest.main()
