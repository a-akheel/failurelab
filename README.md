# FailureLab

[![CI](https://github.com/a-akheel/failurelab/actions/workflows/ci.yml/badge.svg)](https://github.com/a-akheel/failurelab/actions/workflows/ci.yml)

**A small lab for finding where support agents and their workflows fail.**

FailureLab replays support requests, injects tool failures, and keeps the traces behind every score. It also tests [DeskPilot](https://github.com/a-akheel/deskpilot) through its actual Kotlin API and Temporal workflow.

Python · React/Vite · optional Portkey

![FailureLab results and trace inspection](docs/images/dashboard.jpg)

## Try it

Runs locally in demo mode without API keys. Connecting a live model is optional and requires your own credentials.

Python 3.11+ runs the harness without extra Python packages:

```sh
python3 -m unittest discover -s tests -v
python3 -m agent_eval.cli
```

For the dashboard, install Node 22+ and pnpm 11, then run:

```sh
python3 scripts/dev.py
```

Open **http://127.0.0.1:5174**. Switch between **Agent policies** and **DeskPilot integration**. Select a scenario to inspect its trace, or upload a CLI report. The integration view displays a recorded run; it does not silently start infrastructure or make model calls.

## Two different experiments

| Experiment | What it establishes | Result |
|---|---|---|
| 25 support fixtures across VPN, email, and helpdesk | The evaluator detects known failures in deterministic policies | Guarded policy passes; weak policy fails stale-context and injection cases |
| 16 DeskPilot HTTP cases | Workflow outcomes, approval scope, action counts, retry budgets | All passed in the saved run |
| Actual worker-process restart | The pending plan survives JVM replacement and executes once | Passed in the saved run |

Read the [actual integration report](examples/deskpilot-report.json) and [failure analysis](docs/FAILURE_CASES.md). These are **demo/integration results**, not live-model quality claims.

## Run the integration yourself

Clone DeskPilot beside this repository. Install Java 21 and [Temporal CLI](https://docs.temporal.io/cli), then:

```sh
python3 scripts/integration.py --deskpilot ../deskpilot
```

The runner builds DeskPilot, creates isolated temporary databases and role tokens, runs the cases, restarts the worker, writes `reports/deskpilot.json`, and stops its processes. It removes Portkey settings from its child environment. It exits nonzero on a failed check.

## Compare policies or models

```sh
# Expected exit code 1: the deliberately weak policy fails release gates.
python3 -m agent_eval.cli --config configs/comparison.json --output reports/comparison.json
```

Live comparisons use `configs/portkey.example.json` and your own gateway credentials, model, and token prices. See [evaluation design](docs/EVALUATION.md) and the [demo walkthrough](docs/WALKTHROUGH.md).

## Scope

The reference policy uses service keywords; it is not a general language-understanding system. Citation checks verify fresh evidence IDs, not every factual claim. Twenty-five synthetic fixtures are a starting regression set, not a representative production benchmark. The adapter interface receives request text only; expected outcomes and fault labels stay in the evaluator.

MIT licensed.
