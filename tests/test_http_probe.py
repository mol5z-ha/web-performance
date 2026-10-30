import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "http_probe.py"
spec = importlib.util.spec_from_file_location("http_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Handler(BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        self.hits.append(self.path)
        status = 302 if self.path == "/redirect" else 500 if self.path == "/failure" else 200
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "/redirect-target")
        self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("Set-Cookie", "private-cookie")
        self.send_header("Content-Length", "100" if self.path == "/short" else "4")
        self.end_headers()
        self.wfile.write(b"test")

    def log_message(self, *args):
        pass


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_success_and_header_allowlist(self):
        result = probe.probe(self.url + "/")
        self.assertTrue(result["http_ok"])
        self.assertEqual(result["bytes_read"], 4)
        self.assertIn("Cache-Control", result["cache_headers"])
        self.assertNotIn("private-cookie", json.dumps(result))
        self.assertLessEqual(result["headers_ms"], result["total_ms"])

    def test_expected_body_distinguishes_fast_wrong_200(self):
        good = probe.probe(self.url, expected_sha256=hashlib.sha256(b"test").hexdigest())
        bad = probe.probe(self.url, expected_sha256=hashlib.sha256(b"expected business result").hexdigest())
        self.assertTrue(good["content_matches"])
        self.assertTrue(bad["http_ok"])
        self.assertFalse(bad["content_matches"])
        self.assertNotIn("expected business result", json.dumps(bad))

    def test_no_redirect_following(self):
        Handler.hits.clear()
        result = probe.probe(self.url + "/redirect")
        self.assertEqual(result["status"], 302)
        self.assertFalse(result["http_ok"])
        self.assertEqual(Handler.hits, ["/redirect"])

    def test_http_error_is_not_in_success_summary(self):
        failed = probe.probe(self.url + "/failure")
        self.assertEqual(failed["status"], 500)
        summary = probe.summarize([failed, {"http_ok": True, "total_ms": 25}])
        self.assertEqual(summary["complete_2xx_count"], 1)
        self.assertEqual(summary["median_ms"], 25)
        self.assertIsNone(probe.summarize([failed])["median_ms"])

    def test_body_limit_and_exact_boundary(self):
        result = probe.probe(self.url, max_bytes=2)
        self.assertFalse(result["http_ok"])
        self.assertEqual(result["error"], "body_limit_exceeded")
        self.assertTrue(probe.probe(self.url, max_bytes=4)["http_ok"])

    def test_incomplete_body_not_success(self):
        result = probe.probe(self.url + "/short")
        self.assertFalse(result["complete"])
        self.assertFalse(result["http_ok"])

    def test_input_boundaries(self):
        for url in ("file:///tmp/x", "https://user:pass@example.com/", "https://example.com/#x",
                    "http:///", "http://example.com:invalid/", "https://example.com/a b"):
            with self.subTest(url=url), self.assertRaises(argparse.ArgumentTypeError):
                probe.validate_url(url)
        for value in ("0", "11", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                probe.bounded_number(1, 10)(value)

    def test_cli_output_and_exit_codes(self):
        for path, code in (("/?secret=not-for-output", 0), ("/failure", 1)):
            result = subprocess.run([sys.executable, str(SCRIPT), self.url + path,
                                     "--count", "1"], capture_output=True, text=True)
            self.assertEqual(result.returncode, code)
            data = json.loads(result.stdout)
            self.assertEqual(len(data["samples"]), 1)
            self.assertNotIn("not-for-output", result.stdout)

    def test_network_error_does_not_echo_url(self):
        # Reserve then close an ephemeral local port; it should refuse the request.
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        result = probe.probe(f"http://127.0.0.1:{port}/?secret=hidden", timeout=0.2)
        self.assertFalse(result["http_ok"])
        self.assertIsNotNone(result["error"])
        self.assertNotIn("hidden", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
