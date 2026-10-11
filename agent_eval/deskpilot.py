"""Black-box integration: expected outcomes never enter DeskPilot requests."""
import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TERMINAL = {"completed", "failed", "escalated", "rejected", "expired", "stale_approval"}


class DeskPilotClient:
    def __init__(self, base_url, fixture_url, operator, approver, control):
        self.base_url = base_url.rstrip("/")
        self.fixture_url = fixture_url.rstrip("/")
        self.operator, self.approver, self.control = operator, approver, control

    def request(self, base, path, token, body=None):
        request = Request(base + path, None if body is None else json.dumps(body).encode(),
                          {"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    def configure(self, settings):
        return self.request(self.fixture_url, "/__test__/configure", self.control, settings)

    def snapshot(self, incident_id):
        return self.request(self.base_url, "/api/incidents/" + incident_id, self.operator)

    def wait_for(self, incident_id, states, timeout=45):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                snapshot = self.snapshot(incident_id)
                if snapshot["status"] in states:
                    return snapshot
            except HTTPError as exc:
                with exc:
                    if exc.code != 503:
                        raise
            time.sleep(.1)
        raise TimeoutError("DeskPilot did not reach the expected lifecycle boundary")

    def run_case(self, case):
        started = time.perf_counter()
        trace = []
        self.configure(case["fixture"])
        incident = self.request(self.base_url, "/api/incidents", self.operator, case["request"])
        incident_id = incident["id"]
        waiting = self.wait_for(incident_id, TERMINAL | {"awaiting_approval"})
        trace.append({"type": "workflow", "phase": "before_decision", "snapshot": waiting})
        credential_denied = True
        if waiting["status"] == "awaiting_approval":
            decision = {"approved": case.get("approve", True), "planId": waiting["plan"]["id"]}
            path = "/api/incidents/" + incident_id + "/decision"
            # Operators must not approve their own proposed remediation.
            try:
                self.request(self.base_url, path, self.operator, decision)
                credential_denied = False
            except HTTPError as exc:
                with exc:
                    credential_denied = exc.code == 403
            if case.get("before_approval"):
                self.configure(case["before_approval"])
            self.request(self.base_url, path, self.approver, decision)
            if case.get("duplicate_approval"):
                try:
                    self.request(self.base_url, path, self.approver, decision)
                except HTTPError as exc:
                    with exc:
                        if exc.code not in {404, 503}:
                            raise
            final = self.wait_for(incident_id, TERMINAL)
        else:
            final = waiting
        trace.append({"type": "workflow", "phase": "terminal", "snapshot": final})
        stats = self.request(self.fixture_url, "/__test__/stats?" + urlencode({"key": incident_id + ":restart"}), self.control)
        expected = case["expected"]
        checks = {
            "workflow_outcome": final["status"] == expected["status"],
            "action_count": stats["actions"] == expected["actions"],
            "approval_scope": credential_denied,
            "execution_success": True,
        }
        if "reads" in expected:
            checks["retry_budget"] = stats["reads"].get(case["fixture"]["service"], 0) == expected["reads"]
        trace.append({"type": "fixture_ledger", "actions": stats["actions"], "reads": stats["reads"]})
        return {"scenario": case["id"], "fault": case["fixture"].get("fault", "none"),
                "config": "DeskPilot integration", "checks": checks, "passed": all(checks.values()),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "estimated_cost_usd": 0, "output": {"response": final["status"], "incident_id": incident_id},
                "trace": trace, "error": None}


def run_suite(client, cases):
    results = []
    for case in cases:
        try:
            result = client.run_case(case)
        except Exception as exc:
            result = {"scenario": case["id"], "fault": case["fixture"].get("fault", "none"),
                      "config": "DeskPilot integration", "passed": False,
                      "checks": {"execution_success": False}, "error": type(exc).__name__,
                      "latency_ms": 0, "estimated_cost_usd": 0,
                      "output": {"response": "Integration failed"}, "trace": []}
        results.append(result)
    from .scoring import summarize
    summary = summarize(results, {"task_completion": 1.0})
    return {"schema_version": 1, "run_type": "deskpilot_integration_demo", "created_at": datetime.now(timezone.utc).isoformat(),
            "suite_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
            "groups": [{"config": {"name": "DeskPilot integration", "adapter": "deskpilot_http", "model": "deterministic"},
                        "results": results, **summary}], "release_passed": summary["release_passed"]}


def main():
    parser = argparse.ArgumentParser(description="Evaluate the running DeskPilot demo through HTTP")
    parser.add_argument("--suite", default="scenarios/deskpilot.json")
    parser.add_argument("--output", default="reports/deskpilot.json")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--fixture-url", default="http://127.0.0.1:8091")
    args = parser.parse_args()
    client = DeskPilotClient(args.url, args.fixture_url, os.environ["OPERATOR_TOKEN"],
                            os.environ["APPROVER_TOKEN"], os.environ["FIXTURE_CONTROL_TOKEN"])
    report = run_suite(client, json.loads(Path(args.suite).read_text()))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    for row in report["groups"][0]["results"]:
        print("PASS" if row["passed"] else "FAIL", row["scenario"], row["checks"])
    raise SystemExit(0 if report["release_passed"] else 1)


if __name__ == "__main__":
    main()
