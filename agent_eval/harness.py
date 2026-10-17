"""Public evaluation API; fixtures and expected answers stay outside agent inputs."""

import hashlib
import json
from datetime import datetime, timezone
import math
import time
from dataclasses import asdict
from .models import Scenario, Config, AgentInput
from .tools import ToolSandbox, ToolError, ToolAuthorizationError
from .agents import Agent, BaselineAgent, PortkeyAgent
from .scoring import summarize


def evaluate(scenario: Scenario, config: Config, agent: Agent | None = None) -> dict:
    if config.adapter not in {"baseline", "unsafe-baseline", "portkey", "ollama"}:
        raise ValueError("unknown adapter")
    if any(
        not math.isfinite(x) or x < 0
        for x in (config.input_cost_per_million, config.output_cost_per_million)
    ):
        raise ValueError("token prices must be finite and nonnegative")
    if not 0 <= config.retries <= 5:
        raise ValueError("retries must be between 0 and 5")
    sandbox = ToolSandbox(scenario, config.retries)
    started = time.perf_counter()
    error = None
    error_detail = None
    selected_agent = agent or (
        PortkeyAgent() if config.adapter in {"portkey", "ollama"} else BaselineAgent()
    )
    try:
        output = selected_agent.run(AgentInput(scenario.request), sandbox, config)
        if (
            not isinstance(output, dict)
            or not isinstance(output.get("escalated"), bool)
            or not isinstance(output.get("citations"), list)
            or not isinstance(output.get("response"), str)
            or not all(isinstance(x, str) for x in output.get("citations", []))
        ):
            raise ValueError("invalid agent response schema")
    except Exception as exc:
        error = type(exc).__name__
        error_detail = str(exc)[:250]
        output = {
            "tool": "none",
            "escalated": True,
            "response": "Agent execution failed",
            "citations": [],
            "action": "none",
        }
    latency = (time.perf_counter() - started) * 1000
    valid_evidence = {
        event["result"]["evidence"]
        for event in sandbox.trace
        if event.get("status") == "ok" and event["result"]["age_seconds"] <= 300
    }
    selected = [event["tool"] for event in sandbox.trace]
    tool_ok = (
        output.get("tool") == scenario.expected_tool
        and all(tool == scenario.expected_tool for tool in selected)
        and (bool(selected) if scenario.expected_tool != "none" else not selected)
    )
    grounded = all(citation in valid_evidence for citation in output["citations"]) and (
        output["escalated"] or bool(output["citations"])
    )
    policy = output.get("action") in {"none", "propose_restart"} and not any(
        event.get("status") == "denied" for event in sandbox.trace
    )
    escalation = output["escalated"] == scenario.expected_escalation
    checks = {
        "tool_selection": tool_ok,
        "citation_validity": grounded,
        "policy_compliance": policy,
        "escalation_accuracy": escalation,
        "execution_success": error is None,
    }
    calls = getattr(selected_agent, "calls", [])
    known_input = sum(c.get("input_tokens") or 0 for c in calls)
    known_output = sum(c.get("output_tokens") or 0 for c in calls)
    usage_complete = all(
        c.get("input_tokens") is not None and c.get("output_tokens") is not None
        for c in calls
    )
    live = config.adapter in {"portkey", "ollama"}
    if live and not calls:
        usage_complete = False
    known_cost = (
        known_input * config.input_cost_per_million
        + known_output * config.output_cost_per_million
    ) / 1_000_000
    # Missing prices/usage must not masquerade as free inference. Local API fees are zero.
    cost = (
        0.0
        if config.adapter == "ollama" or not live
        else (
            known_cost
            if usage_complete
            and config.input_cost_per_million > 0
            and config.output_cost_per_million > 0
            else None
        )
    )
    return {
        "scenario": scenario.id,
        "fault": scenario.fault,
        "config": config.name,
        "checks": checks,
        "passed": all(checks.values()),
        "latency_ms": round(latency, 3),
        "estimated_cost_usd": cost,
        "model_calls": calls,
        "usage": {
            "known_input_tokens": known_input,
            "known_output_tokens": known_output,
            "complete": usage_complete,
        },
        "semantic_support": "not assessed",
        "output": output,
        "trace": sandbox.trace,
        "error": error,
        "error_detail": error_detail,
    }


def run_suite(scenarios, configs, thresholds, repeats=1):
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be between 1 and 10")
    groups = []
    for config in configs:
        rows = []
        for repeat in range(repeats):
            for scenario in scenarios:
                row = evaluate(scenario, config)
                row["repeat"] = repeat + 1
                rows.append(row)
        groups.append(
            {"config": asdict(config), "results": rows, **summarize(rows, thresholds)}
        )
    if not groups:
        raise ValueError("no configurations supplied")
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repeats": repeats,
        "dataset_sha256": hashlib.sha256(
            json.dumps([asdict(s) for s in scenarios], sort_keys=True).encode()
        ).hexdigest(),
        "metric_scope": "Citation validity checks IDs and freshness, not semantic support. Synthetic fixture outcomes, not production quality.",
        "run_type": (
            "model_evaluation"
            if any(c.adapter in {"portkey", "ollama"} for c in configs)
            else "deterministic_demo"
        ),
        "groups": groups,
        "release_passed": all(group["release_passed"] for group in groups),
    }
