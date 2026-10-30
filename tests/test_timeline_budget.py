import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "timeline_budget.py"
spec = importlib.util.spec_from_file_location("timeline_budget", SCRIPT)
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


def fixture():
    return {"nodes": [
        {"id": "html", "duration_ms": 150, "depends_on": []},
        {"id": "js", "duration_ms": 200, "depends_on": ["html"]},
        {"id": "api", "duration_ms": 700, "depends_on": ["js"]},
        {"id": "render", "duration_ms": 200, "depends_on": ["api"]},
        {"id": "image", "duration_ms": 1800, "depends_on": ["html"]}],
        "target": "render", "optimize": "api", "goal_ms": 900}


class TimelineTests(unittest.TestCase):
    def test_parallel_image_not_on_actionable_target(self):
        result = budget.calculate(fixture())
        self.assertEqual(result["baseline_target_ms"], 1250)
        self.assertEqual(result["zero_duration_target_ms"], 550)
        self.assertEqual(result["maximum_possible_reduction_ms"], 700)
        self.assertEqual(result["maximum_allowed_node_duration_ms"], 350)
        self.assertEqual(result["required_reduction_ms"], 350)
        self.assertIsNone(result["predicted_achievable_duration_ms"])

    def test_independent_branch_makes_goal_impossible(self):
        data = fixture()
        data["nodes"].append({"id": "ready", "duration_ms": 0, "depends_on": ["render", "image"]})
        data["target"] = "ready"
        result = budget.calculate(data)
        self.assertEqual(result["baseline_target_ms"], 1950)
        self.assertEqual(result["maximum_possible_reduction_ms"], 0)
        self.assertFalse(result["goal_reachable_by_this_node_alone"])
        self.assertIsNone(result["maximum_allowed_node_duration_ms"])

    def test_irrelevant_optimization_has_no_benefit(self):
        data = fixture()
        data["optimize"] = "image"
        result = budget.calculate(data)
        self.assertFalse(result["optimize_affects_target"])
        self.assertEqual(result["maximum_possible_reduction_ms"], 0)

    def test_merge_uses_longest_dependency_not_sum(self):
        data = {"nodes": [{"id": "a", "duration_ms": 10, "depends_on": []},
                          {"id": "b", "duration_ms": 30, "depends_on": []},
                          {"id": "c", "duration_ms": 5, "depends_on": ["a", "b"]}],
                "target": "c", "optimize": "b", "goal_ms": 25}
        result = budget.calculate(data)
        self.assertEqual(result["baseline_target_ms"], 35)
        self.assertEqual(result["zero_duration_target_ms"], 15)
        self.assertEqual(result["maximum_allowed_node_duration_ms"], 20)

    def test_rejects_cycles_missing_duplicate_and_invalid_duration(self):
        mutations = [lambda d: d["nodes"][0]["depends_on"].append("render"),
                     lambda d: d["nodes"][0]["depends_on"].append("missing"),
                     lambda d: d["nodes"].append(copy.deepcopy(d["nodes"][0])),
                     lambda d: d["nodes"][0].update(duration_ms=-1),
                     lambda d: d["nodes"][0].update(duration_ms=float("nan")),
                     lambda d: d["nodes"][0].update(duration_ms=True),
                     lambda d: d.update(goal_ms=float("inf")),
                     lambda d: d.update(nodes=d["nodes"] * 201)]
        for mutate in mutations:
            data = fixture()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                budget.calculate(data)

    def test_finite_nodes_with_overflowing_path_reject_cli_without_traceback(self):
        data = {"nodes": [{"id": "a", "duration_ms": 1e308, "depends_on": []},
                          {"id": "b", "duration_ms": 1e308, "depends_on": ["a"]}],
                "target": "b", "optimize": "a", "goal_ms": 1e308}
        with self.assertRaises(ValueError):
            budget.calculate(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["valid"])
            self.assertEqual(result.stderr, "")

    def test_deep_json_rejected_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.json"
            path.write_text("[" * 1200 + "0" + "]" * 1200, encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["valid"])
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
