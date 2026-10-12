#!/usr/bin/env python3
"""Run the deterministic evaluation API and dashboard; no model credentials needed."""

from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if not shutil.which("pnpm"):
    raise SystemExit("Install Node 22+ and pnpm 11 first.")
subprocess.run(
    ["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"],
    cwd=ROOT / "web",
    check=True,
)
processes = []
try:
    processes.append(
        subprocess.Popen([sys.executable, "-m", "agent_eval.server"], cwd=ROOT)
    )
    processes.append(
        subprocess.Popen(["pnpm", "--dir", "web", "dev", "--port", "5174"], cwd=ROOT)
    )
    print("FailureLab: http://127.0.0.1:5174 · Stop with Ctrl-C", flush=True)
    while all(process.poll() is None for process in processes):
        time.sleep(0.5)
    raise RuntimeError("A service exited; check the output above for a port conflict.")
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
