import json
import unittest

from src.idea_vending.bridge_contract import BRIDGE_VERSION
from src.idea_vending.bridge_request import create_forge_package
from src.idea_vending.bridge_runtime import validate_and_run_forge_import
from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.intent_planner import RESEARCH_PLAN_CATEGORIES
from tests.test_evolution_runtime import FakeIdeationProvider, NOW


IDEA = "고객 반복업무를 사전에 감지해서 자동으로 처리하는 운영 시스템을 만들고 싶다"
SESSION_ID = "br_abcdefghijklmnop"


def evidence_draft(ref, evidence_type, direction, *, families=None):
    return {
        "bridge_claim_ref": ref,
        "claim": f"Evidence for {ref}",
        "source_title": f"Source {ref}",
        "source_url": f"https://example.com/{ref}",
        "publisher": "Example Research",
        "publication_date": "2026-08-01",
        "geography": "Global",
        "population_or_market_definition": "Enterprise AI workflow software",
        "evidence_type": evidence_type,
        "supports_or_contradicts": direction,
        "confidence_tier": "A" if direction == "supports" else "B",
        "freshness_status": "current",
        "candidate_families": list(families or []),
        "notes": "Bridge evidence with explicit provenance.",
        "raw_excerpt": "Untrusted source excerpt.",
        "market_size": None,
    }


def valid_forge_result():
    fake = FakeIdeationProvider()
    evidence_summary = [
        {"claim_id": "bc_support01"},
        {"claim_id": "bc_counter01"},
    ]
    operations = {}
    for operation in (
        "extract_assumptions",
        "challenge_assumptions",
        "propose_reframes",
        "discover_mechanisms",
        "forge_candidates",
    ):
        operations[operation] = fake.generate(
            {"operation": operation, "evidence_summary": evidence_summary}
        )
    family_order = {family: index for index, family in enumerate(sorted(CANDIDATE_FAMILIES))}
    operations["forge_candidates"]["candidates"].sort(
        key=lambda candidate: family_order[candidate["family"]]
    )
    return {
        "landscape_research": [
            evidence_draft("bc_support01", "market_status", "supports"),
            evidence_draft("bc_counter01", "counter_evidence", "contradicts"),
        ],
        **operations,
        "collision_research": [
            evidence_draft(
                "bc_prior01",
                "prior_art",
                "supports",
                families=sorted(CANDIDATE_FAMILIES),
            ),
            evidence_draft(
                "bc_compete01",
                "competitors",
                "supports",
                families=sorted(CANDIDATE_FAMILIES),
            ),
            evidence_draft(
                "bc_block01",
                "failure_or_blockers",
                "contradicts",
                families=sorted(CANDIDATE_FAMILIES),
            ),
        ],
    }


class BridgeForgeTests(unittest.TestCase):
    def test_forge_package_is_secret_free_and_requires_exact_ten_families(self):
        package = create_forge_package(IDEA, SESSION_ID, NOW)
        self.assertEqual(package["bridge_version"], BRIDGE_VERSION)
        self.assertEqual(package["request_type"], "forge")
        self.assertEqual(package["bridge_session_id"], SESSION_ID)
        self.assertEqual(package["candidate_family_contract"], sorted(CANDIDATE_FAMILIES))
        serialized = json.dumps(package, ensure_ascii=False)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("best_candidate", serialized)
        self.assertNotIn("official_decision", serialized)
        instruction = package["chatgpt_instruction"]
        for phrase in ("current web research", "counter-evidence", "exactly ten", "bridge_claim_ref"):
            self.assertIn(phrase, instruction)

    def test_valid_forge_import_replays_through_existing_deterministic_runtime(self):
        envelope = {
            "bridge_session_id": SESSION_ID,
            "bridge_version": BRIDGE_VERSION,
            "result": valid_forge_result(),
        }
        session = {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"}
        forge = validate_and_run_forge_import(session, envelope, now_provider=lambda: NOW)
        self.assertEqual(len(forge["candidates"]), 10)
        self.assertEqual({item["family"] for item in forge["candidates"]}, CANDIDATE_FAMILIES)
        self.assertIsNone(forge["state"]["decision"])
        self.assertTrue(all(record["provider_metadata"]["provider"] == "chatgpt_plus_bridge" for record in forge["evidence_graph"]["records"]))
        self.assertTrue(all(record["provider_metadata"]["source_verification"] == "user_mediated" for record in forge["evidence_graph"]["records"]))

    def test_valid_forge_import_reuses_server_derived_intent_context(self):
        envelope = {
            "bridge_session_id": SESSION_ID,
            "bridge_version": BRIDGE_VERSION,
            "result": valid_forge_result(),
        }
        session = {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"}
        forge = validate_and_run_forge_import(session, envelope, now_provider=lambda: NOW)

        self.assertEqual(forge["intent_model"]["primary_objective"], IDEA)
        self.assertEqual(forge["state"]["normalized_intent"], IDEA)
        self.assertIsNone(forge["intent_model"]["primary_buyer"])
        self.assertIn("primary_buyer", forge["intent_model"]["material_unknowns"])
        self.assertEqual(
            set(forge["research_plan"]["research_questions"]),
            set(RESEARCH_PLAN_CATEGORIES),
        )

    def test_execution_package_pasted_as_forge_result_is_rejected_precisely(self):
        package = create_forge_package(IDEA, SESSION_ID, NOW)
        envelope = {
            "bridge_session_id": SESSION_ID,
            "bridge_version": BRIDGE_VERSION,
            "result": package,
        }
        session = {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"}

        with self.assertRaisesRegex(ValueError, "bridge_forge_package_pasted_as_result"):
            validate_and_run_forge_import(session, envelope, now_provider=lambda: NOW)

    def test_missing_family_and_trusted_id_injection_are_rejected(self):
        for mutate in ("missing_family", "trusted_id"):
            result = valid_forge_result()
            if mutate == "missing_family":
                result["forge_candidates"]["candidates"].pop()
            else:
                result["forge_candidates"]["candidates"][0]["candidate_id"] = "cand_attacker"
            envelope = {
                "bridge_session_id": SESSION_ID,
                "bridge_version": BRIDGE_VERSION,
                "result": result,
            }
            session = {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"}
            with self.assertRaises(ValueError):
                validate_and_run_forge_import(session, envelope, now_provider=lambda: NOW)

    def test_bad_source_and_missing_collision_category_are_rejected(self):
        bad_source = valid_forge_result()
        bad_source["landscape_research"][0]["source_url"] = "javascript:alert(1)"
        missing_collision = valid_forge_result()
        missing_collision["collision_research"] = missing_collision["collision_research"][:2]
        for result in (bad_source, missing_collision):
            with self.assertRaises(ValueError):
                validate_and_run_forge_import(
                    {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"},
                    {"bridge_session_id": SESSION_ID, "bridge_version": BRIDGE_VERSION, "result": result},
                    now_provider=lambda: NOW,
                )

    def test_out_of_order_candidate_families_are_rejected_precisely(self):
        result = valid_forge_result()
        candidates = result["forge_candidates"]["candidates"]
        candidates[0], candidates[1] = candidates[1], candidates[0]

        with self.assertRaisesRegex(ValueError, "bridge_candidate_family_order_invalid"):
            validate_and_run_forge_import(
                {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"},
                {"bridge_session_id": SESSION_ID, "bridge_version": BRIDGE_VERSION, "result": result},
                now_provider=lambda: NOW,
            )

    def test_forward_collision_claim_reference_is_rejected_precisely(self):
        result = valid_forge_result()
        result["forge_candidates"]["candidates"][0]["evidence_claim_ids"] = ["bc_prior01"]
        with self.assertRaisesRegex(ValueError, "bridge_claim_reference_unknown"):
            validate_and_run_forge_import(
                {"bridge_session_id": SESSION_ID, "raw_idea": IDEA, "state": "forge_requested"},
                {"bridge_session_id": SESSION_ID, "bridge_version": BRIDGE_VERSION, "result": result},
                now_provider=lambda: NOW,
            )


if __name__ == "__main__":
    unittest.main()
