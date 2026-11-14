import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "uptime-kuma-monitor-portability")
EX = os.path.join(ROOT, "examples", "in")


def run(args, cwd=None):
    return subprocess.run([sys.executable, BIN] + args, capture_output=True, text=True, cwd=cwd)


def write(tmp, name, payload):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload if isinstance(payload, str) else json.dumps(payload))
    return path


def monitor(**over):
    base = {"id": 9, "name": "x", "type": "http", "active": True, "parent": None,
            "childrenIDs": [], "tags": [], "path": ["x"], "pathName": "x",
            "interval": 60, "weight": None}
    base.update(over)
    return base


class Behaviour(unittest.TestCase):
    def test_example_snapshot_reports_not_portable(self):
        r = run(["audit", "--input", os.path.join(EX, "api-monitors.json")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("not_recreatable=3", r.stdout)

    def test_json_parses_and_counts(self):
        r = run(["audit", "--input", os.path.join(EX, "api-monitors.json"), "--json"])
        rep = json.loads(r.stdout)
        self.assertEqual(rep["summary"]["monitors"], 3)
        self.assertEqual(rep["summary"]["recreatable"], 0)
        self.assertEqual(rep["summary"]["api_fields"], 11)
        self.assertEqual(rep["summary"]["model_fields"], 77)

    def test_http_missing_fields_are_exact(self):
        rep = json.loads(run(["audit", "--input", os.path.join(EX, "api-monitors.json"), "--json"]).stdout)
        http = rep["monitors"][0]
        self.assertEqual(http["missing"], ["accepted_statuscodes", "maxredirects", "method", "url"])

    def test_witness_is_one_minimal(self):
        rep = json.loads(run(["audit", "--input", os.path.join(EX, "api-monitors.json"), "--json"]).stdout)
        for m in rep["monitors"]:
            self.assertEqual(m["witness"], sorted(m["missing"]))
            self.assertTrue(m["missing"])

    def test_push_monitor_is_recreatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "s.json", {"monitors": [monitor(type="push")]})
            r = run(["audit", "--input", p, "--json"])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["summary"]["recreatable"], 1)

    def test_unknown_type_is_warning_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "s.json", {"monitors": [monitor(type="quantum-probe")]})
            r = run(["audit", "--input", p, "--json"])
        rep = json.loads(r.stdout)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any(f["code"] == "W_UNKNOWN_TYPE" for f in rep["findings"]))

    def test_type_error_is_detected(self):
        r = run(["audit", "--input", os.path.join(EX, "bad-snapshot.json"), "--json"])
        rep = json.loads(r.stdout)
        self.assertEqual(r.returncode, 1)
        fields = sorted(f["field"] for f in rep["findings"] if f["code"] == "E_SCHEMA")
        self.assertEqual(fields, ["active", "childrenIDs", "id"])

    def test_template_contains_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "tpl.json")
            r = run(["audit", "--input", os.path.join(EX, "api-monitors.json"),
                     "--json", "--emit-template", out])
            self.assertEqual(r.returncode, 1)
            tpl = json.load(open(out, encoding="utf-8"))
        self.assertEqual(tpl["monitors"][0]["fill_required"],
                         {"accepted_statuscodes": None, "maxredirects": None, "method": None, "url": None})

    def test_missing_file_is_usage_error(self):
        r = run(["audit", "--input", "/nonexistent/snapshot.json"])
        self.assertEqual(r.returncode, 2)

    def test_invalid_json_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "bad.json", "{not json")
            r = run(["audit", "--input", p])
        self.assertEqual(r.returncode, 2)

    def test_missing_monitors_key_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "s.json", {"ok": True})
            r = run(["audit", "--input", p])
        self.assertEqual(r.returncode, 2)

    def test_report_is_deterministic(self):
        a = run(["audit", "--input", os.path.join(EX, "api-monitors.json"), "--json"]).stdout
        b = run(["audit", "--input", os.path.join(EX, "api-monitors.json"), "--json"]).stdout
        self.assertEqual(a, b)

    def test_empty_monitor_list_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write(tmp, "s.json", {"monitors": []})
            r = run(["audit", "--input", p, "--json"])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["summary"]["monitors"], 0)


if __name__ == "__main__":
    unittest.main()
