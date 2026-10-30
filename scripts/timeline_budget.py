"""Compute a measured dependency timeline's budget, never a predicted optimization speed."""
import argparse
import json
import math
from pathlib import Path


def finite_nonnegative(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def calculate(data):
    if not isinstance(data, dict):
        raise ValueError("object_required")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 1000:
        raise ValueError("requires_1_to_1000_nodes")
    graph = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("invalid_node")
        key = node.get("id")
        deps = node.get("depends_on")
        if (not isinstance(key, str) or not key or key in graph
                or not finite_nonnegative(node.get("duration_ms"))
                or not isinstance(deps, list) or len(deps) > 1000
                or any(not isinstance(dep, str) for dep in deps)
                or len(set(deps)) != len(deps)):
            raise ValueError("invalid_or_duplicate_node")
        graph[key] = node
    target, optimize, goal = data.get("target"), data.get("optimize"), data.get("goal_ms")
    if not isinstance(target, str) or not isinstance(optimize, str) or target not in graph or optimize not in graph:
        raise ValueError("unknown_target_or_optimize")
    if not finite_nonnegative(goal):
        raise ValueError("invalid_goal")
    children = {key: [] for key in graph}
    degree = {}
    for key, node in graph.items():
        degree[key] = len(node["depends_on"])
        for dep in node["depends_on"]:
            if dep not in graph:
                raise ValueError("missing_dependency")
            children[dep].append(key)
    ready = [key for key in graph if degree[key] == 0]
    order = []
    while ready:
        key = ready.pop()
        order.append(key)
        for child in children[key]:
            degree[child] -= 1
            if degree[child] == 0:
                ready.append(child)
    if len(order) != len(graph):
        raise ValueError("cycle")

    # Every target path either avoids optimize, or contains it once.
    # Propagate the maximum path length in each class. A path containing
    # optimize has length duration(optimize) + the measured remainder.
    avoiding, through = {}, {}
    for key in order:
        node = graph[key]
        deps = node["depends_on"]
        a = max((avoiding[d] for d in deps), default=0.0)
        b = max((through[d] for d in deps), default=-math.inf)
        if key == optimize:
            avoiding[key] = -math.inf
            through[key] = a
        else:
            avoiding[key] = a + node["duration_ms"]
            through[key] = b + node["duration_ms"]
        if any(math.isinf(v) and v > 0 for v in (avoiding[key], through[key])):
            raise ValueError("timeline_overflow")
    remainder, independent = through[target], avoiding[target]
    duration = graph[optimize]["duration_ms"]
    baseline = max(independent, remainder + duration)
    theoretical_minimum = max(independent, remainder)
    relevant = remainder != -math.inf
    reachable = theoretical_minimum <= goal
    budget = goal - remainder if relevant and reachable else None
    if not all(math.isfinite(value) for value in (baseline, theoretical_minimum)) or (budget is not None and not math.isfinite(budget)):
        raise ValueError("timeline_overflow")
    return {"baseline_target_ms": baseline,
            "zero_duration_target_ms": theoretical_minimum,
            "maximum_possible_reduction_ms": baseline - theoretical_minimum,
            "optimize_affects_target": relevant,
            "goal_reachable_by_this_node_alone": reachable,
            "maximum_allowed_node_duration_ms": budget,
            "required_reduction_ms": max(0, duration - budget) if budget is not None else None,
            "predicted_achievable_duration_ms": None,
            "interpretation": "Budget under supplied measured DAG and unchanged other durations; not predicted achievable speed. Null budget means impossible or irrelevant; inspect flags."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    args = parser.parse_args()
    try:
        with args.timeline.open("rb") as handle:
            raw = handle.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("input_too_large")
        result = calculate(json.loads(raw.decode("utf-8-sig")))
    except (ValueError, TypeError, OSError, OverflowError, RecursionError):
        print(json.dumps({"valid": False, "error": "invalid_timeline"}))
        return 2
    print(json.dumps({"valid": True, **result}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
