import unittest

from src.idea_vending.bridge_request import create_forge_package, create_judge_package
from src.idea_vending.intent_planner import RESEARCH_PLAN_CATEGORIES
from tests.test_bridge_forge import IDEA, SESSION_ID
from tests.test_bridge_judge import trusted_forge
from tests.test_evolution_runtime import NOW


class BridgePromptContractTests(unittest.TestCase):
    def test_forge_package_exposes_complete_section_schemas_and_vocabularies(self):
        package = create_forge_package(IDEA, SESSION_ID, NOW)
        contract = package["result_contract"]
        schemas = contract["section_schemas"]
        self.assertEqual(
            set(schemas),
            {
                "landscape_research",
                "extract_assumptions",
                "challenge_assumptions",
                "propose_reframes",
                "discover_mechanisms",
                "forge_candidates",
                "collision_research",
            },
        )
        evidence = schemas["landscape_research"]["items"]
        self.assertEqual(evidence["additionalProperties"], False)
        self.assertIn("bridge_claim_ref", evidence["required"])
        self.assertIn("candidate_families", evidence["required"])
        candidate = schemas["forge_candidates"]["properties"]["candidates"]["items"]
        self.assertEqual(len(candidate["properties"]["family"]["enum"]), 10)
        assumption = schemas["extract_assumptions"]["properties"]["assumptions"]["items"]
        self.assertIn("workflow", assumption["properties"]["assumption_type"]["enum"])
        self.assertIn("contested", assumption["properties"]["status"]["enum"])
        transformation = schemas["propose_reframes"]["properties"]["transformations"]["items"]
        self.assertIn("REPAIR_TO_PREVENT", transformation["properties"]["transformation"]["enum"])
        self.assertIn("material", transformation["properties"]["materiality"]["enum"])

    def test_forge_package_exposes_iso_publication_date_contract(self):
        package = create_forge_package(IDEA, SESSION_ID, NOW)
        publication_date = (
            package["result_contract"]["section_schemas"]["landscape_research"]
            ["items"]["properties"]["publication_date"]
        )
        self.assertEqual(publication_date["type"], "string")
        self.assertEqual(publication_date["pattern"], r"^\d{4}-\d{2}-\d{2}$")

    def test_forge_instruction_forbids_forward_collision_claim_references(self):
        package = create_forge_package(IDEA, SESSION_ID, NOW)
        instruction = package["chatgpt_instruction"]
        self.assertIn("collision evidence cannot be referenced", instruction)
        self.assertIn("landscape_research", instruction)
        self.assertIn("YYYY-MM-DD", instruction)

    def test_forge_package_contains_server_derived_intent_and_question_only_plan(self):
        package = create_forge_package(IDEA, SESSION_ID, NOW)
        context = package["intent_context"]
        intent = context["intent_model"]
        plan = context["research_plan"]

        self.assertEqual(intent["primary_objective"], IDEA)
        self.assertIsNone(intent["primary_buyer"])
        self.assertIn("primary_buyer", intent["material_unknowns"])
        self.assertIn("success_metrics", intent["material_unknowns"])
        self.assertEqual(
            set(plan["research_questions"]),
            set(RESEARCH_PLAN_CATEGORIES),
        )
        self.assertEqual(set(plan), {"research_questions"})

        instruction = package["chatgpt_instruction"]
        self.assertIn(IDEA, instruction)
        self.assertIn("Hard constraints", instruction)
        self.assertIn("Success metrics", instruction)
        self.assertIn("Material unknowns", instruction)
        self.assertIn("research questions", instruction.lower())

        contract = package["result_contract"]
        self.assertEqual(
            set(contract["required_top_level_keys"]),
            {
                "landscape_research",
                "extract_assumptions",
                "challenge_assumptions",
                "propose_reframes",
                "discover_mechanisms",
                "forge_candidates",
                "collision_research",
            },
        )

    def test_judge_package_exposes_exact_critique_and_additional_evidence_schemas(self):
        package = create_judge_package(trusted_forge(), SESSION_ID, NOW)
        contract = package["result_contract"]
        schema = contract["result_schema"]
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(set(schema["required"]), {"critiques", "additional_evidence"})
        critique = schema["properties"]["critiques"]["items"]
        self.assertEqual(critique["additionalProperties"], False)
        self.assertEqual(
            set(critique["properties"]["recommendation"]["enum"]),
            {"advance", "revise", "hold", "reject"},
        )
        dimension = critique["properties"]["dimensions"]["items"]
        self.assertEqual(
            set(dimension["properties"]["status"]["enum"]),
            {"strong", "mixed", "weak", "unknown"},
        )
        blocker = dimension["properties"]["blockers"]["items"]
        self.assertEqual(
            set(blocker["properties"]["materiality"]["enum"]),
            {"minor", "material", "hard"},
        )
        evidence = schema["properties"]["additional_evidence"]["items"]
        self.assertIn("bridge_claim_ref", evidence["required"])
        self.assertEqual(evidence["additionalProperties"], False)


if __name__ == "__main__":
    unittest.main()
