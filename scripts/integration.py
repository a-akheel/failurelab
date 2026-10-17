#!/usr/bin/env python3
"""Start isolated local dependencies, run the HTTP suite, then stop owned processes."""

import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deskpilot", type=Path, default=ROOT.parent / "deskpilot")
    parser.add_argument("--temporal", default=shutil.which("temporal"))
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--output", default=str(ROOT / "reports/deskpilot.json"))
    args = parser.parse_args()
    desk = args.deskpilot.resolve()
    if not args.temporal or not (desk / "gradlew").exists():
        parser.error(
            "Install Temporal CLI and provide the DeskPilot checkout with --deskpilot"
        )
    env = dict(os.environ)
    env["LLM_PROVIDER"] = "demo"
    # Integration reports are always the free deterministic planner, even if the shell has model keys.
    for key in list(env):
        if key.startswith("PORTKEY_"):
            del env[key]
    env.update(
        {
            key: secrets.token_urlsafe(24)
            for key in (
                "OPERATOR_TOKEN",
                "APPROVER_TOKEN",
                "IT_API_TOKEN",
                "FIXTURE_CONTROL_TOKEN",
            )
        }
    )
    api_port, it_port, temporal_port, ui_port = [unused_port() for _ in range(4)]
    env.update(
        PORT=str(api_port),
        IT_PORT=str(it_port),
        IT_API_URL=f"http://127.0.0.1:{it_port}",
        TEMPORAL_ADDRESS=f"127.0.0.1:{temporal_port}",
    )
    if not args.skip_build:
        subprocess.run(
            [str(desk / "gradlew"), "installDist", "--no-daemon"],
            cwd=desk,
            env=env,
            check=True,
        )
    processes = []
    with tempfile.TemporaryDirectory(prefix="failurelab-") as tmp:
        tmp = Path(tmp)
        env["IT_DB"] = str(tmp / "fixture.db")
        logs = []
        try:
            commands = [
                (
                    [
                        args.temporal,
                        "server",
                        "start-dev",
                        "--ip",
                        "127.0.0.1",
                        "--port",
                        str(temporal_port),
                        "--ui-port",
                        str(ui_port),
                        "--db-filename",
                        str(tmp / "temporal.db"),
                    ],
                    desk,
                ),
                ([sys.executable, str(desk / "demo/it_api.py")], desk),
                ([str(desk / "build/install/deskpilot/bin/deskpilot")], desk),
            ]
            # Temporal needs to be accepting connections before the worker starts.
            for index, (command, cwd) in enumerate(commands):
                log = open(tmp / f"process-{index}.log", "w+")
                logs.append(log)
                processes.append(
                    subprocess.Popen(
                        command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                )
                if index == 0:
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        try:
                            with socket.create_connection(
                                ("127.0.0.1", temporal_port), timeout=1
                            ):
                                break
                        except OSError:
                            time.sleep(0.2)
                    else:
                        raise TimeoutError("Temporal startup failed")
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                try:
                    request = Request(
                        f"http://127.0.0.1:{api_port}/api/health",
                        headers={"Authorization": "Bearer " + env["OPERATOR_TOKEN"]},
                    )
                    with urlopen(request, timeout=2):
                        break
                except OSError:
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError("A demo dependency exited before readiness")
                    time.sleep(0.2)
            else:
                raise TimeoutError("DeskPilot startup failed")
            command = [
                sys.executable,
                "-m",
                "agent_eval.deskpilot",
                "--url",
                f"http://127.0.0.1:{api_port}",
                "--fixture-url",
                env["IT_API_URL"],
                "--output",
                args.output,
            ]
            result = subprocess.run(command, cwd=ROOT, env=env)
            if result.returncode:
                return result.returncode
            # Verify recovery by terminating the actual Kotlin worker/API process.
            sys.path.insert(0, str(ROOT))
            from agent_eval.deskpilot import DeskPilotClient, TERMINAL
            import json

            client = DeskPilotClient(
                f"http://127.0.0.1:{api_port}",
                env["IT_API_URL"],
                env["OPERATOR_TOKEN"],
                env["APPROVER_TOKEN"],
                env["FIXTURE_CONTROL_TOKEN"],
            )
            client.configure(
                {"service": "vpn", "status": "degraded", "revision": "restart-test"}
            )
            incident = client.request(
                client.base_url,
                "/api/incidents",
                client.operator,
                {
                    "service": "vpn",
                    "description": "VPN unavailable during a worker restart",
                },
            )
            waiting = client.wait_for(incident["id"], {"awaiting_approval"})
            processes[-1].terminate()
            processes[-1].wait(timeout=15)
            command, cwd = commands[-1]
            processes[-1] = subprocess.Popen(
                command, cwd=cwd, env=env, stdout=logs[-1], stderr=subprocess.STDOUT
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    restored = client.snapshot(incident["id"])
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                raise TimeoutError("Replacement worker did not restore the incident")
            client.request(
                client.base_url,
                "/api/incidents/" + incident["id"] + "/decision",
                client.approver,
                {"approved": True, "planId": waiting["plan"]["id"]},
            )
            final = client.wait_for(incident["id"], TERMINAL)
            stats = client.request(
                client.fixture_url,
                "/__test__/stats?key=" + incident["id"] + ":restart",
                client.control,
            )
            checks = {
                "workflow_outcome": final["status"] == "completed",
                "action_count": stats["actions"] == 1,
                "plan_preserved": restored["plan"]["id"] == waiting["plan"]["id"],
                "execution_success": True,
            }
            report_path = Path(args.output)
            report = json.loads(report_path.read_text())
            report["recovery_test"] = {
                "passed": all(checks.values()),
                "checks": checks,
                "before_restart": waiting,
                "after_restart": restored,
                "terminal": final,
            }
            report["release_passed"] = report["release_passed"] and all(checks.values())
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            print(
                "PASS" if all(checks.values()) else "FAIL",
                "worker-process-restart",
                checks,
            )
            return 0 if report["release_passed"] else 1
        except Exception:
            for log in logs:
                log.flush()
                log.seek(0)
                print(log.read()[-4000:], file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()


if __name__ == "__main__":
    raise SystemExit(main())
