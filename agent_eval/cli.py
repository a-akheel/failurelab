import argparse, json
from pathlib import Path
from .harness import Scenario, Config, run_suite

def main():
    parser=argparse.ArgumentParser(description="Replay agent scenarios and enforce release gates")
    parser.add_argument("--suite",default="scenarios/support.json")
    parser.add_argument("--config",default="configs/baseline.json")
    parser.add_argument("--output",default="reports/latest.json")
    args=parser.parse_args()
    spec=json.loads(Path(args.config).read_text())
    scenarios=[Scenario(**row) for row in json.loads(Path(args.suite).read_text())]
    report=run_suite(scenarios,[Config(**row) for row in spec["configurations"]],spec["thresholds"])
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    for group in report["groups"]:
        print(group["config"]["name"],json.dumps(group["metrics"]),"PASS" if group["release_passed"] else "FAIL")
    raise SystemExit(0 if report["release_passed"] else 1)
if __name__=="__main__": main()
