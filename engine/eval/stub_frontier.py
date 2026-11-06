"""Stands in for a frontier model API during the egress test. Records what it receives."""
import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with open("/tmp/seen.jsonl", "a") as f:
            f.write(json.dumps(body["input"], ensure_ascii=False) + "\n")
        data = [{"index": i, "embedding": [random.random() for _ in range(64)]} for i in range(len(body["input"]))]
        out = json.dumps({"data": data}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


HTTPServer(("0.0.0.0", 9000), H).serve_forever()
