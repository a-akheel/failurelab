"""Public evaluation API; fixtures and expected answers stay outside agent inputs."""

import math
import time
from dataclasses import asdict
from .models import Scenario, Config, AgentInput
from .tools import ToolSandbox, ToolError, ToolAuthorizationError
from .agents import Agent, BaselineAgent, PortkeyAgent
from .scoring import summarize


def evaluate(scenario: Scenario, config: Config, agent: Agent | None = None) -> dict:
    if config.adapter not in {"baseline", "unsafe-baseline", "portkey"}:
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
    try:
        output = (
            agent
            or (PortkeyAgent() if config.adapter == "portkey" else BaselineAgent())
        ).run(AgentInput(scenario.request), sandbox, config)
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
        "grounded": grounded,
        "policy_compliance": policy,
        "escalation_accuracy": escalation,
        "execution_success": error is None,
    }
    cost = (
        output.get("input_tokens", 0) * config.input_cost_per_million
        + output.get("output_tokens", 0) * config.output_cost_per_million
    ) / 1_000_000
    return {
        "scenario": scenario.id,
        "fault": scenario.fault,
        "config": config.name,
        "checks": checks,
        "passed": all(checks.values()),
        "latency_ms": round(latency, 3),
        "estimated_cost_usd": cost,
        "output": output,
        "trace": sandbox.trace,
        "error": error,
    }


def run_suite(scenarios, configs, thresholds):
    groups = []
    for config in configs:
        rows = [evaluate(scenario, config) for scenario in scenarios]
        groups.append(
            {"config": asdict(config), "results": rows, **summarize(rows, thresholds)}
        )
    if not groups:
        raise ValueError("no configurations supplied")
    return {
        "schema_version": 1,
        "run_type": (
            "model_evaluation"
            if any(c.adapter == "portkey" for c in configs)
            else "deterministic_demo"
        ),
        "groups": groups,
        "release_passed": all(group["release_passed"] for group in groups),
    }
