import unittest
from agent_eval.harness import Config, Scenario, evaluate, run_suite

class BoundaryTests(unittest.TestCase):
    def test_agent_input_contains_no_expected_answers_or_fault(self):
        class Inspect:
            def run(self, request, tools, config):
                assert set(vars(request)) == {"request"}
                return {"tool":"none","escalated":True,"response":"Clarify service","citations":[],"action":"none"}
        row=evaluate(Scenario("ambiguous","Something broke","ambiguous","none",True),Config("test"),Inspect())
        self.assertTrue(row["passed"])

    def test_bad_citation_type_is_a_failed_run_not_a_crash(self):
        class Broken:
            def run(self,*args):
                return {"tool":"none","escalated":False,"response":"ok","citations":[{}],"action":"none"}
        self.assertFalse(evaluate(Scenario("test","VPN failed","none","service_status",False),Config("test"),Broken())["passed"])

    def test_wrong_service_does_not_pass(self):
        row=evaluate(Scenario("test","Email failed","none","service_status",False,service="vpn"),Config("test"))
        self.assertFalse(row["passed"])

    def test_ambiguous_multi_service_request_escalates(self):
        row=evaluate(Scenario("test","VPN and email failed","none","none",True),Config("test"))
        self.assertTrue(row["passed"])

    def test_invalid_prices_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(Scenario("test","VPN failed","none","service_status",False),Config("test",input_cost_per_million=-1))

    def test_run_labels_distinguish_demo_from_models(self):
        report=run_suite([Scenario("test","VPN failed","none","service_status",False)],[Config("test")],{"task_completion":1})
        self.assertEqual("deterministic_demo",report["run_type"])
