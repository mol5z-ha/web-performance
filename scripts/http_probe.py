#!/usr/bin/env python3
"""Small sequential HTTP probe, not a browser benchmark or load test."""

import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(value):
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or any(ord(c) <= 32 for c in value)):
            raise ValueError()
        _ = parsed.port
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Use an HTTP(S) URL without user information, fragments or whitespace."
        ) from None
    return value


def bounded_number(low, high, integer=False):
    def parse(value):
        try:
            number = int(value) if integer else float(value)
            if not math.isfinite(number) or not low <= number <= high:
                raise ValueError()
            return number
        except ValueError:
            raise argparse.ArgumentTypeError(f"Expected a number in [{low}, {high}].") from None
    return parse


def probe(url, timeout=10, max_bytes=2 * 1024 * 1024):
    start = time.perf_counter()
    result = {"status": None, "complete": False, "http_ok": False,
              "headers_ms": None, "total_ms": None, "bytes_read": 0,
              "cache_headers": {}, "error": None}
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={
        "User-Agent": "web-performance-probe/1.0",
        "Accept-Encoding": "identity",
    })
    try:
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            result["status"] = response.code
            result["headers_ms"] = round((time.perf_counter() - start) * 1000, 2)
            result["cache_headers"] = {
                key: response.headers[key] for key in ("Cache-Control", "Age", "Vary")
                if response.headers.get(key) is not None
            }
            # Read one extra byte to distinguish an exact-size response from truncation.
            while result["bytes_read"] <= max_bytes:
                chunk = response.read(min(65536, max_bytes + 1 - result["bytes_read"]))
                if not chunk:
                    result["complete"] = True
                    break
                result["bytes_read"] += len(chunk)
            if not result["complete"]:
                result["error"] = "body_limit_exceeded"
            else:
                length = response.headers.get("Content-Length")
                if length and length.isdigit() and int(length) != result["bytes_read"]:
                    result["complete"] = False
                    result["error"] = "content_length_mismatch"
            result["http_ok"] = result["complete"] and 200 <= response.code < 300
    except Exception as error:
        # No raw message: exception text can contain private URLs or proxy details.
        result["complete"] = False
        result["http_ok"] = False
        result["error"] = type(error).__name__
    result["total_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return result


def summarize(samples):
    values = [sample["total_ms"] for sample in samples if sample["http_ok"]]
    return {"complete_2xx_count": len(values),
            "min_ms": min(values) if values else None,
            "median_ms": round(statistics.median(values), 2) if values else None,
            "max_ms": max(values) if values else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", type=validate_url)
    parser.add_argument("--count", type=bounded_number(1, 10, True), default=3)
    parser.add_argument("--interval", type=bounded_number(0.1, 60), default=1)
    parser.add_argument("--timeout", type=bounded_number(0.1, 60), default=10)
    parser.add_argument("--max-bytes", type=bounded_number(1, 8388608, True), default=2097152)
    args = parser.parse_args()
    samples = []
    for index in range(args.count):
        if index:
            time.sleep(args.interval)
        samples.append(probe(args.url, args.timeout, args.max_bytes))
    print(json.dumps({"schema_version": 1,
                      "measurement": "sequential HTTP GET; no redirects or browser rendering",
                      "samples": samples, "summary": summarize(samples)}, indent=2))
    return 0 if all(sample["http_ok"] for sample in samples) else 1


if __name__ == "__main__":
    raise SystemExit(main())
