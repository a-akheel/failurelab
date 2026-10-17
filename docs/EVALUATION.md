# Evaluation design

## Module boundaries

- `models.py`: scenario/configuration records and the request-only agent input.
- `tools.py`: scope checks, fault injection, retries, and traces.
- `agents.py`: deterministic policies and optional Ollama and Portkey adapters.
- `scoring.py`: aggregated metrics and fail-closed release thresholds.
- `harness.py`: execution and per-case checks.
- `deskpilot.py`: actual HTTP workflow evaluation.

Expected tools, escalation decisions, and fixture faults are never included in `AgentInput`. The weak policy responds to the injected text it sees, rather than reading the hidden fault label. This is an interface boundary, not a security sandbox against malicious Python code introspecting its own process.

## Metrics

Task completion means every check for a case passed. Tool selection verifies the selected tool and actual attempts. Citation validity requires fresh cited IDs for non-escalated responses; it does not measure semantic support. Policy checks prohibit actions outside the supported proposal vocabulary and denied tool calls. Escalation compares against the fixture expectation. p95 is nearest-rank wall-clock latency. Estimated API cost multiplies returned input/output token usage by configured prices. Missing paid-provider usage or prices produces null, not zero. Local Ollama has zero API fees; hardware and electricity are excluded.

Integration checks have different names: workflow outcome, action count, approval scope, and retry budget where applicable. The process-restart check additionally verifies the plan ID survives. Do not compare integration latency directly with in-process policy latency.

## Reproducibility

Integration reports contain a UTC timestamp, SHA-256 of the ordered scenario fixture content, before/after workflow snapshots, and ledger counts. The runner creates isolated state and removes model credentials from child environments. Local validation used Temporal CLI 1.9.1, Java 21, and Python 3.14. CI uses Java 21 and Python 3.12.

## Live models

Copy `configs/portkey.example.json`, set a real model name, prompt, retries, and current token prices. Export `PORTKEY_API_KEY` and `PORTKEY_VIRTUAL_KEY`, then run `python3 -m agent_eval.cli --config configs/my-model.json --output reports/model.json`. Use multiple configuration entries for comparisons. Report files may contain prompt and response text; review them before publishing.

Recorded Qwen3 4B runs are included in `examples/qwen3-comparison.json` and `examples/qwen3-guarded.json`. The dashboard exposes the unguarded comparison separately from the deterministic policies. Zero demo cost means no model was called. A failed provider call can incur charges not represented by returned usage.

```sh
ollama pull qwen3:4b
python3 -m agent_eval.cli --config configs/ollama.json --repeats 2 --output reports/model.json
python3 -m agent_eval.cli --config configs/ollama-guarded.json --repeats 2 --output reports/guarded.json
```

These commands intentionally exit nonzero when release gates fail. Reports retain per-call usage, errors, parsed outputs, prompts, repetitions and a dataset hash. Publish only synthetic/public inputs. The same 25 development scenarios are reused across configurations, not an independent holdout. Two repetitions are not enough to establish statistical significance.

`enforce_evidence` applies deterministic evidence checks after a model proposal. Raw proposals are preserved so system-level gains cannot be misrepresented as better model reasoning. It cannot resolve ambiguous requests or verify factual support in prose. No proposed action is executed by this evaluator.

## Limits worth testing next

Broader paraphrases, multi-step tool choices, network disconnects, rate limits, model nondeterminism across repeated trials, and independent semantic grounding checks. Current timeout fixtures raise errors or return HTTP 504; they do not model actual elapsed network timeout duration.
