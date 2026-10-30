import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_http.py"
spec = importlib.util.spec_from_file_location("compare_http", SCRIPT)
compare_http = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_http)


def report(revision, times):
    return {"schema_version": 1,
            "measurement": "sequential HTTP GET; no redirects or browser rendering",
            "condition": "same data/cache/operation", "revision": revision,
            "expected_sha256": "a" * 64,
            "samples": [{"total_ms": t, "http_ok": True, "complete": True,
                         "content_matches": True, "status": 200} for t in times]}


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.before = report("old", [100, 110, 120])
        self.after = report("new", [45, 55, 65])

    def test_known_change_not_supplied_summary(self):
        self.before["summary"] = {"median_ms": 1}
        result = compare_http.compare(self.before, self.after)
        self.assertTrue(result["comparable"])
        self.assertEqual(result["median_change_percent"], -50)
        self.assertFalse(result["ranges_overlap"])
        self.assertEqual(result["performance_conclusion"], "observed_faster")

    def test_fast_wrong_content_and_failed_samples_block_claim(self):
        for field, value in (("content_matches", False), ("http_ok", False), ("complete", False),
                             ("total_ms", float("nan")), ("status", 500), ("total_ms", True)):
            after = copy.deepcopy(self.after)
            after["samples"][0][field] = value
            result = compare_http.compare(self.before, after)
            self.assertFalse(result["comparable"])
            self.assertIsNone(result["median_change_percent"])

    def test_incompatible_conditions_or_body_are_rejected(self):
        for field, value in (("condition", "cold-cache"), ("revision", "old"),
                             ("expected_sha256", "b" * 64), ("schema_version", 2),
                             ("samples", []), ("samples", [None, None, None])):
            after = copy.deepcopy(self.after)
            after[field] = value
            self.assertFalse(compare_http.compare(self.before, after)["comparable"])

    def test_regression_is_positive_and_overlapping_ranges_visible(self):
        result = compare_http.compare(self.before, report("new", [100, 220, 300]))
        self.assertEqual(result["median_change_percent"], 100)
        self.assertTrue(result["ranges_overlap"])
        self.assertEqual(result["performance_conclusion"], "inconclusive")

    def test_finite_samples_with_overflowing_ratio_reject_comparison(self):
        result = compare_http.compare(report("old", [1e-300] * 3), report("new", [1e300] * 3))
        self.assertFalse(result["comparable"])
        self.assertIsNone(result["median_change_percent"])
        json.dumps(result, allow_nan=False)

    def test_cli_invalid_json_has_no_traceback_or_private_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-example.json"
            path.write_text("broken", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["comparable"])
            self.assertNotIn(directory, result.stdout + result.stderr)

    def test_cli_handles_extreme_integer_and_nesting(self):
        inputs = [json.dumps(report("old", [10 ** 400] * 3)), "[" * 1200 + "0" + "]" * 1200]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            for raw in inputs:
                path.write_text(raw, encoding="utf-8")
                result = subprocess.run([sys.executable, str(SCRIPT), str(path), str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)["comparable"])
                self.assertEqual(result.stderr, "")

    def test_demo_preserves_independent_expected_content_and_changes_plan(self):
        result = subprocess.run([sys.executable, str(SCRIPT.with_name("demo_index.py"))], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["comparison"]["comparable"])
        self.assertTrue(all(s["content_matches"] for r in (data["before"], data["after"]) for s in r["samples"]))
        self.assertNotEqual(data["query_plans"][0], data["query_plans"][1])
        # Timing is deliberately not asserted: shared CI runners have variable noise.


if __name__ == "__main__":
    unittest.main()
