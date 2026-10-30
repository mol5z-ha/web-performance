"""Loopback-only reproducible SQLite index experiment; emits raw before/after evidence."""
import hashlib
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time

from http_probe import probe, summarize
from compare_http import compare


def run():
    with tempfile.TemporaryDirectory(prefix="web-performance-demo-") as directory:
        database = Path(directory) / "demo.sqlite3"
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, category INTEGER, title TEXT)")
            connection.executemany("INSERT INTO items VALUES (?, ?, ?)",
                                   ((i, i % 1000, f"item-{i}") for i in range(100000)))
            connection.commit()
        query = "SELECT id, title FROM items WHERE category = 999 ORDER BY id LIMIT 20"
        expected = json.dumps([[i, f"item-{i}"] for i in range(999, 20000, 1000)]).encode()
        digest = hashlib.sha256(expected).hexdigest()
        db_samples = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with closing(sqlite3.connect(database)) as connection:
                    started = time.perf_counter()
                    rows = connection.execute(query).fetchall()
                    db_samples.append(round((time.perf_counter() - started) * 1000, 4))
                    body = json.dumps(rows).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            reports = []
            plans = []
            for revision in ("table-scan", "category-index"):
                with closing(sqlite3.connect(database)) as connection:
                    if revision == "category-index":
                        connection.execute("CREATE INDEX items_category ON items(category)")
                        connection.commit()
                    plans.append([row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + query)])
                samples = [probe(f"http://127.0.0.1:{server.server_port}/", expected_sha256=digest)
                           for _ in range(7)]
                reports.append({"schema_version": 1,
                                "measurement": "sequential HTTP GET; no redirects or browser rendering",
                                "condition": "loopback; 100000 rows; category 999; first 20 by id; cache not reset",
                                "revision": revision, "expected_sha256": digest,
                                "samples": samples, "summary": summarize(samples),
                                "db_execute_fetch_ms": db_samples[-7:]})
            return {"experiment": "SQLite query index; fixed independent expected response",
                    "query_plans": plans, "before": reports[0], "after": reports[1],
                    "comparison": compare(*reports),
                    "db_measurement": "sqlite execute + fetchall only; excludes connect, JSON, HTTP and rendering",
                    "limits": "Fixed before-after order and OS cache confound timing; query plans establish changed access path. No browser or production claim."}
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
