import json
import unittest

from src.idea_vending.bridge_contract import BRIDGE_VERSION
from src.idea_vending.bridge_request import create_judge_package
from src.idea_vending.bridge_runtime import (
    validate_and_finalize_judge_import,
    validate_and_run_forge_import,
)
from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from tests.test_bridge_forge import IDEA, SESSION_ID, valid_forge_result
from tests.test_evolution_runtime import FakeEvaluationProvider, NOW


def trusted_forge():
    return validate_and_run_forge_import(
        {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"},
        {
            "bridge_session_id": SESSION_ID,
            "bridge_version": BRIDGE_VERSION,
            "result": valid_forge_result(),
        },
        now_provider=lambda: NOW,
    )


def valid_judge_result(forge, scenario="go"):
    provider = FakeEvaluationProvider(scenario)
    raw = provider.evaluate(
        {
            "evidence_graph": forge["evidence_graph"],
            "baseline": forge["baseline"],
            "candidates": forge["candidates"],
        }
    )
    return {"critiques": raw["critiques"], "additional_evidence": []}


class BridgeJudgeTests(unittest.TestCase):
    def test_judge_package_contains_trusted_context_but_no_generator_preference_or_official_fields(self):
        forge = trusted_forge()
        package = create_judge_package(forge, SESSION_ID, NOW)
        self.assertEqual(package["bridge_version"], BRIDGE_VERSION)
        self.assertEqual(package["request_type"], "judge")
        self.assertEqual(len(package["candidates"]), 10)
        self.assertEqual(set(package["evaluation_dimensions"]), EVALUATION_DIMENSIONS)
        serialized = json.dumps(package, ensure_ascii=False)
        for forbidden in (
            "preferred_candidate",
            '"ranking"',
            '"score"',
            '"human_decision"',
            '"official_decision"',
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("fresh ChatGPT conversation", package["chatgpt_instruction"])

    def test_valid_judge_import_reaches_same_deterministic_go_path(self):
        forge = trusted_forge()
        envelope = {
            "bridge_session_id": SESSION_ID,
            "bridge_version": BRIDGE_VERSION,
            "result": valid_judge_result(forge, "go"),
        }
        completed = validate_and_finalize_judge_import(
            {
                "bridge_session_id": SESSION_ID,
                "raw_idea": IDEA,
                "state": "judge_requested",
                "trusted_forge": forge,
            },
            envelope,
            now_provider=lambda: NOW,
        )
        self.assertEqual(completed["runtime"]["status"], "completed")
        self.assertEqual(completed["state"]["decision"], "GO")
        self.assertEqual(len(completed["candidate_reality_assessments"]), 10)

    def test_judge_requires_baseline_plus_exactly_ten_candidate_critiques(self):
        forge = trusted_forge()
        result = valid_judge_result(forge)
        result["critiques"].pop()
        with self.assertRaises(ValueError):
            validate_and_finalize_judge_import(
                {
                    "bridge_session_id": SESSION_ID,
                    "raw_idea": IDEA,
                    "state": "judge_requested",
                    "trusted_forge": forge,
                },
                {
                    "bridge_session_id": SESSION_ID,
                    "bridge_version": BRIDGE_VERSION,
                    "result": result,
                },
                now_provider=lambda: NOW,
            )

    def test_judge_official_field_injection_and_wrong_state_are_rejected(self):
        forge = trusted_forge()
        result = valid_judge_result(forge)
        result["decision"] = "GO"
        for state, payload in (
            ("judge_requested", result),
            ("forge_validated", valid_judge_result(forge)),
        ):
            with self.assertRaises(ValueError):
                validate_and_finalize_judge_import(
                    {
                        "bridge_session_id": SESSION_ID,
                        "raw_idea": IDEA,
                        "state": state,
                        "trusted_forge": forge,
                    },
                    {
                        "bridge_session_id": SESSION_ID,
                        "bridge_version": BRIDGE_VERSION,
                        "result": payload,
                    },
                    now_provider=lambda: NOW,
                )

    def test_judge_critique_must_cover_all_evaluator_dimensions(self):
        forge = trusted_forge()
        result = valid_judge_result(forge)
        result["critiques"][0]["dimensions"].pop()
        with self.assertRaises(ValueError):
            validate_and_finalize_judge_import(
                {
                    "bridge_session_id": SESSION_ID,
                    "raw_idea": IDEA,
                    "state": "judge_requested",
                    "trusted_forge": forge,
                },
                {
                    "bridge_session_id": SESSION_ID,
                    "bridge_version": BRIDGE_VERSION,
                    "result": result,
                },
                now_provider=lambda: NOW,
            )


if __name__ == "__main__":
    unittest.main()
