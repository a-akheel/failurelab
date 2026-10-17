"""Local dashboard API. Executes only the bundled deterministic configs."""

import json, os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .harness import Scenario, Config, run_suite

ROOT = Path(__file__).resolve().parent.parent


def demo():
    scenarios = [
        Scenario(**row)
        for row in json.loads((ROOT / "scenarios/support.json").read_text())
    ]
    spec = json.loads((ROOT / "configs/comparison.json").read_text())
    return run_suite(
        scenarios, [Config(**row) for row in spec["configurations"]], spec["thresholds"]
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/report":
            report = demo()
        elif self.path == "/api/integration-report":
            report = json.loads((ROOT / "examples/deskpilot-report.json").read_text())
        elif self.path == "/api/model-report":
            report = json.loads((ROOT / "examples/qwen3-comparison.json").read_text())
        else:
            self.send_error(404)
            return
        data = json.dumps(report).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print("Evaluation API: http://127.0.0.1:8090")
    ThreadingHTTPServer(
        ("127.0.0.1", int(os.getenv("EVAL_API_PORT", "8090"))), Handler
    ).serve_forever()
