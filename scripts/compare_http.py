"""Compare two probe reports; refuse timing conclusions when evidence is incompatible."""
import argparse
import json
import math
from pathlib import Path
import statistics


def compare(before, after):
    reasons = []
    if not before.get("condition") or before.get("condition") != after.get("condition"):
        reasons.append("conditions_missing_or_different")
    if not before.get("revision") or not after.get("revision") or before["revision"] == after["revision"]:
        reasons.append("distinct_revisions_required")
    digest = before.get("expected_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or digest != after.get("expected_sha256"):
        reasons.append("same_verified_body_required")
    expected_measurement = "sequential HTTP GET; no redirects or browser rendering"
    values = []
    for label, report in (("before", before), ("after", after)):
        if report.get("schema_version") != 1 or report.get("measurement") != expected_measurement:
            reasons.append(label + "_unsupported_measurement")
        samples = report.get("samples")
        if not isinstance(samples, list) or not 3 <= len(samples) <= 10:
            reasons.append(label + "_requires_3_to_10_samples")
            values.append([])
            continue
        times = []
        for sample in samples:
            if not isinstance(sample, dict):
                reasons.append(label + "_invalid_sample")
                continue
            value = sample.get("total_ms")
            if (sample.get("http_ok") is not True or sample.get("complete") is not True
                    or sample.get("content_matches") is not True
                    or type(sample.get("status")) is not int or not 200 <= sample["status"] < 300
                    or type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                reasons.append(label + "_failed_or_unverified_sample")
            else:
                times.append(value)
        values.append(times)
    if reasons:
        return {"comparable": False, "reasons": sorted(set(reasons)), "median_change_percent": None}
    a, b = values
    old, new = statistics.median(a), statistics.median(b)
    change = (new - old) / old * 100
    if not all(math.isfinite(value) for value in (old, new, change)):
        return {"comparable": False, "reasons": ["computed_value_overflow"], "median_change_percent": None}
    overlap = max(min(a), min(b)) <= min(max(a), max(b))
    return {"comparable": True, "reasons": [],
            "before": {"count": len(a), "median_ms": old, "range_ms": [min(a), max(a)]},
            "after": {"count": len(b), "median_ms": new, "range_ms": [min(b), max(b)]},
            "median_change_percent": round(change, 2),
            "change_percent_kind": "descriptive_sample_medians_only",
            "ranges_overlap": overlap,
            "performance_conclusion": "inconclusive" if overlap else "observed_faster" if new < old else "observed_slower",
            "interpretation": "Descriptive local HTTP comparison; overlap is a conservative reporting rule, not a significance test. Even separated ranges do not prove causality, browser speed, p95 or a population guarantee."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    try:
        reports = [json.loads(p.read_text(encoding="utf-8-sig")) for p in (args.before, args.after)]
        if any(not isinstance(r, dict) for r in reports):
            raise ValueError()
        result = compare(*reports)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        print(json.dumps({"comparable": False, "reasons": ["invalid_report"]}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["comparable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
