# Demo walkthrough

1. Run `python3 scripts/dev.py` and open http://127.0.0.1:5174.
2. In Agent policies, switch from Guarded baseline to Weak baseline. Inspect an injection or stale-context failure.
3. Explain the distinction: these policies test the evaluator, not model quality.
4. Select DeskPilot integration. Inspect `lost-action-response`, `evidence-changed-after-approval`, and `authorization-not-retried`.
5. Expand the trace: workflow snapshots and ledger counts are evidence behind the pass/fail result.
6. Point out the actual worker-process restart result and the preserved plan ID.
7. Rerun `python3 scripts/integration.py --deskpilot ../deskpilot`, then upload `reports/deskpilot.json` to view fresh results.

Model comparison is a separate, explicitly paid experiment. Do not describe the deterministic report as a benchmark of a live model.
