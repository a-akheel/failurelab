import unittest
from unittest.mock import patch
from agent_eval.agents import PortkeyAgent
from agent_eval.harness import Config, Scenario, evaluate
from agent_eval.scoring import summarize


class UsageTests(unittest.TestCase):
    def test_partial_usage_survives_second_call_failure(self):
        class Partial(PortkeyAgent):
            def _portkey_complete(self, messages, config, record):
                if len(self.calls) == 1:
                    record.update(input_tokens=120, output_tokens=10)
                    return {"tool": "service_status", "service": "vpn"}, {
                        "prompt_tokens": 120,
                        "completion_tokens": 10,
                    }
                raise TimeoutError("provider timed out")

        row = evaluate(
            Scenario("x", "VPN failed", "none", "service_status", False),
            Config(
                "test",
                adapter="portkey",
                input_cost_per_million=1,
                output_cost_per_million=2,
            ),
            Partial(),
        )
        self.assertFalse(row["passed"])
        self.assertEqual(row["usage"]["known_input_tokens"], 120)
        self.assertFalse(row["usage"]["complete"])
        self.assertIsNone(row["estimated_cost_usd"])
        self.assertFalse(summarize([row], {"estimated_cost_usd": 1})["release_passed"])
        self.assertEqual(
            [c["status"] for c in row["model_calls"]], ["completed", "failed"]
        )

    def test_valid_citation_does_not_claim_semantic_support(self):
        class Fabricator:
            def run(self, request, tools, config):
                data = tools.call("service_status", "vpn")
                return {
                    "tool": "service_status",
                    "escalated": False,
                    "citations": [data["evidence"]],
                    "response": "An unsupported statement",
                    "action": "none",
                }

        row = evaluate(
            Scenario("x", "VPN failed", "none", "service_status", False),
            Config("test"),
            Fabricator(),
        )
        self.assertTrue(row["checks"]["citation_validity"])
        self.assertEqual(row["semantic_support"], "not assessed")

    def test_truncated_local_response_is_failure(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return b'{"done":true,"done_reason":"length","prompt_eval_count":20,"eval_count":5}'

        class Opener:
            def open(self, *args, **kwargs):
                return Response()

        agent = PortkeyAgent()
        with patch("urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(ValueError):
                agent.complete([], Config("local", adapter="ollama", model="qwen3:4b"))
        self.assertEqual(agent.calls[0]["input_tokens"], 20)
        self.assertEqual(agent.calls[0]["status"], "failed")

    def test_repeats_are_bounded(self):
        from agent_eval.harness import run_suite

        with self.assertRaises(ValueError):
            run_suite([], [], {}, repeats=0)


class EvidenceGuardTests(unittest.TestCase):
    def test_fresh_id_does_not_allow_restart_after_tool_failure(self):
        class Unsafe(PortkeyAgent):
            def complete(self, messages, config):
                if "Select a tool" in messages[0]["content"]:
                    return {"tool": "service_status", "service": "vpn"}, {}
                return {
                    "response": "Restart now",
                    "escalated": False,
                    "citations": ["monitor:vpn:001"],
                    "action": "propose_restart",
                }, {}

        for fault in ("timeout", "stale", "unauthorized", "malformed"):
            row = evaluate(
                Scenario("x", "VPN failed", fault, "service_status", True),
                Config("guarded", enforce_evidence=True),
                Unsafe(),
            )
            self.assertEqual(row["output"]["action"], "none")
            self.assertTrue(row["output"]["escalated"])
            self.assertEqual(row["output"]["raw_proposal"]["action"], "propose_restart")
