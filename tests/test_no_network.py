"""No-network enforcement: with sockets blocked, generating,
estimating, gating, sizing and reporting must all still work.
(``serve`` is the only intentional exception - it binds loopback on
demand, and is not used here.)"""

import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Blocker:
    def __init__(self, *a, **k):
        raise RuntimeError("network access blocked in hermetic test")


class TestNoNetwork(unittest.TestCase):
    def setUp(self):
        self._real_socket = socket.socket
        socket.socket = _Blocker
        import urllib.request as urlreq
        self._real_urlopen = urlreq.urlopen
        urlreq.urlopen = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("network access blocked in hermetic test"))

    def tearDown(self):
        socket.socket = self._real_socket
        import urllib.request as urlreq
        urlreq.urlopen = self._real_urlopen

    def test_full_pipeline_offline(self):
        from generator import generate_scenario
        from report import build_report
        from validation import validate_dataset
        rows = generate_scenario("clean")
        self.assertEqual(validate_dataset(rows), [])
        report = build_report(rows)
        self.assertEqual(report["clean"]["gate"]["verdict"], "PASS")

    def test_no_module_opens_sockets_at_import(self):
        for mod in ("generator", "statsmath", "classifier", "holdout",
                    "gate", "sizing", "validation", "report", "cli", "demo"):
            sys.modules.pop(mod, None)
        import cli, classifier, demo, gate, generator, holdout  # noqa: F401
        import report, sizing, statsmath, validation  # noqa: F401
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
