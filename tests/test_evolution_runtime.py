import unittest

from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from src.idea_vending.evidence_graph import create_evidence_record
from src.idea_vending.evolution_runtime import run_evolution
from src.idea_vending.provider_transport import ProviderTimeout


NOW = "2026-09-16T06:00:00+00:00"
TODAY = "2026-09-16"


def make_evidence(
    evidence_id,
    claim_id,
    evidence_type,
    direction,
    *,
    candidate_ids=None,
    confidence="A",
):
    return create_evidence_record(
        evidence_id=evidence_id,
        claim_id=claim_id,
        claim=f"Evidence claim {claim_id}",
        source_title=f"Source {claim_id}",
        source_url=f"https://example.com/{claim_id}",
        publisher="Example Research",
        publication_date="2026-08-01",
        retrieved_at=TODAY,
        geography="Global",
        population_or_market_definition="Enterprise AI workflow software",
        evidence_type=evidence_type,
        supports_or_contradicts=direction,
        confidence_tier=confidence,
        freshness_status="current",
        candidate_ids=list(candidate_ids or []),
        notes="Test evidence with explicit provenance.",
        raw_content_untrusted="Untrusted source excerpt.",
        provider_metadata={"provider": "fake-research"},
        market_size=None,
    )


class FakeResearchProvider:
    def __init__(self):
        self.calls = []

    def research(self, request):
        self.calls.append(request["pass_type"])
        if request["pass_type"] == "landscape":
            records = [
                make_evidence(
                    "ev_landscape01",
                    "claim_landscape01",
                    "market_status",
                    "supports",
                ),
                make_evidence(
                    "ev_counter001",
                    "claim_counter001",
                    "counter_evidence",
                    "contradicts",
                    confidence="B",
                ),
            ]
            run_id = "research_landscape_run"
        else:
            ids = request["candidate_ids"]
            records = [
                make_evidence(
                    "ev_priorart01",
                    "claim_priorart01",
                    "prior_art",
                    "supports",
                    candidate_ids=ids,
                ),
                make_evidence(
                    "ev_compete001",
                    "claim_compete001",
                    "competitors",
                    "supports",
                    candidate_ids=ids,
                    confidence="B",
                ),
                make_evidence(
                    "ev_blockers01",
                    "claim_blockers01",
                    "failure_or_blockers",
                    "contradicts",
                    candidate_ids=ids,
                ),
            ]
            run_id = "research_collision_run"
        return {
            "provider": "fake-research",
            "provider_run_id": run_id,
            "records": records,
            "metadata": {
                "model": "fake-research-model",
                "usage": {},
                "source_count": len(records),
            },
        }


class TimeoutResearchProvider:
    def research(self, request):
        raise ProviderTimeout("provider request timed out")


class FakeIdeationProvider:
    def __init__(self):
        self.calls = []
        self.last_run_metadata = None
        self._sequence = 0

    def _mark(self, operation):
        self._sequence += 1
        self.last_run_metadata = {
            "provider": "fake-ideation",
            "provider_response_id": f"ideation_{self._sequence}",
            "model": "fake-reasoner",
            "operation": operation,
            "usage": {},
            "source_count": None,
        }

    def generate(self, request):
        operation = request["operation"]
        self.calls.append(operation)
        self._mark(operation)
        claims = [item["claim_id"] for item in request["evidence_summary"]]
        support = claims[0] if claims else None
        counter = claims[1] if len(claims) > 1 else None

        if operation == "extract_assumptions":
            return {
                "assumptions": [
                    {
                        "statement": "The workflow should remain reactive.",
                        "assumption_type": "workflow",
                        "scope": "Customer operations",
                        "why_it_exists": "Current teams respond only after demand appears.",
                        "supporting_claim_ids": [support] if support else [],
                        "contradicting_claim_ids": [counter] if counter else [],
                        "status": "contested",
                    },
                    {
                        "statement": "Users must manually provide every input.",
                        "assumption_type": "customer_behavior",
                        "scope": "Input collection",
                        "why_it_exists": "Legacy tools depend on explicit forms.",
                        "supporting_claim_ids": [],
                        "contradicting_claim_ids": [counter] if counter else [],
                        "status": "weak",
                    },
                ]
            }
        if operation == "challenge_assumptions":
            return {
                "challenges": [
                    {
                        "assumption_index": 0,
                        "challenge_question": "What if the workflow acted before the request?",
                        "remove_or_invert_test": "Invert reactive into preventive operation.",
                        "expected_effect_if_false": "Less downstream manual work.",
                        "new_opportunity_if_false": "Prevention workflow.",
                        "new_risk_if_false": "False-positive intervention.",
                    },
                    {
                        "assumption_index": 1,
                        "challenge_question": "What if inputs were observed automatically?",
                        "remove_or_invert_test": "Replace manual input with observation.",
                        "expected_effect_if_false": "Lower user effort.",
                        "new_opportunity_if_false": "Ambient workflow automation.",
                        "new_risk_if_false": "Permission and privacy risk.",
                    },
                ]
            }
        if operation == "propose_reframes":
            return {
                "transformations": [
                    {
                        "transformation": "REPAIR_TO_PREVENT",
                        "applicable": True,
                        "reason": "Prevention can remove repeated downstream handling.",
                        "resulting_reframe": "Prevent recurring work before it reaches operators.",
                        "materiality": "material",
                    },
                    {
                        "transformation": "INPUT_TO_OBSERVE",
                        "applicable": True,
                        "reason": "Observed signals can replace repetitive forms.",
                        "resulting_reframe": "Observe operational signals instead of waiting for inputs.",
                        "materiality": "material",
                    },
                ]
            }
        if operation == "discover_mechanisms":
            return {
                "mechanisms": [
                    {
                        "source_domain": "Preventive maintenance",
                        "mechanism_name": "Leading-indicator intervention",
                        "mechanism_description": "Act on leading signals before failure.",
                        "source_constraint": "Failure is expensive after it occurs.",
                        "why_it_works_there": "Observable precursors appear before failure.",
                        "target_equivalent_constraint": "Customer work is costly after requests arrive.",
                        "transfer_logic": "Use precursor signals to intervene before repetitive work appears.",
                        "value_chain_change": "Reactive handling becomes preventive workflow control.",
                        "expected_customer_value": "Lower recurring operating effort.",
                        "new_risks": ["False-positive interventions"],
                        "supporting_claim_ids": [support] if support else [],
                    },
                    {
                        "source_domain": "Fraud detection",
                        "mechanism_name": "Continuous signal observation",
                        "mechanism_description": "Observe events continuously rather than wait for reports.",
                        "source_constraint": "Manual reporting arrives too late.",
                        "why_it_works_there": "Event streams expose changes immediately.",
                        "target_equivalent_constraint": "Manual input delays customer operations.",
                        "transfer_logic": "Replace explicit input with bounded operational observation.",
                        "value_chain_change": "Input collection becomes continuous detection.",
                        "expected_customer_value": "Faster, lower-friction workflow execution.",
                        "new_risks": ["Data-access boundaries"],
                        "supporting_claim_ids": [support] if support else [],
                    },
                ]
            }
        if operation == "forge_candidates":
            families = [
                "adjacent_innovation",
                "category_shift",
                "zero_based_reinvention",
                "axion_candidate",
            ]
            candidates = []
            for index, family in enumerate(families):
                candidates.append(
                    {
                        "family": family,
                        "name": f"Candidate {index}",
                        "one_sentence_concept": f"Distinct evolved concept {index} for automated operations.",
                        "problem_reframe": f"Distinct problem frame {index}",
                        "primary_buyer": f"Buyer segment {index}",
                        "user": f"Operator segment {index}",
                        "job_to_be_done": f"Complete operational job {index} with less manual work.",
                        "assumption_indexes": [index % 2],
                        "transformations_used": [
                            "REPAIR_TO_PREVENT" if index % 2 == 0 else "INPUT_TO_OBSERVE"
                        ],
                        "mechanism_indexes": [index % 2],
                        "workflow_before": f"Manual reactive workflow {index}",
                        "workflow_after": f"Automated preventive workflow {index}",
                        "value_creation_chain": {
                            "current_constraint": f"Constraint {index}",
                            "intervention": f"Intervention {index}",
                            "workflow_or_incentive_change": f"Workflow change {index}",
                            "operational_or_economic_effect": f"Economic effect {index}",
                            "buyer_value": f"Buyer value {index}",
                            "value_capture": f"Value capture {index}",
                        },
                        "value_capture_model": f"Outcome-linked project value {index}",
                        "automation_thesis": f"Automate repeated work stream {index}",
                        "defensibility_thesis": f"Evidence and workflow learning loop {index}",
                        "compounding_effect": f"Validated operational knowledge compounds {index}",
                        "critical_dependencies": [f"Dependency {index}"],
                        "new_risks": [f"Risk {index}"],
                        "evidence_claim_ids": [support] if support else [],
                        "unknowns": [f"Unknown {index}"],
                        "validation_questions": [f"Validation question {index}?"],
                    }
                )
            return {"candidates": candidates}
        raise AssertionError(f"unexpected operation: {operation}")


class BrokenIdeationProvider(FakeIdeationProvider):
    def generate(self, request):
        raise RuntimeError("unexpected internal adapter failure")


class FakeEvaluationProvider:
    def __init__(self, scenario):
        self.scenario = scenario
        self.last_run_metadata = None

    def evaluate(self, request):
        self.last_run_metadata = {
            "provider": "fake-evaluation",
            "provider_response_id": f"judge_{self.scenario}",
            "model": "fake-judge",
            "operation": "independent_evaluation",
            "usage": {},
            "source_count": None,
        }
        graph = request["evidence_graph"]
        support = next(
            record["claim_id"]
            for record in graph["records"]
            if record["supports_or_contradicts"] == "supports"
        )
        contradiction = next(
            record["claim_id"]
            for record in graph["records"]
            if record["supports_or_contradicts"] == "contradicts"
        )
        targets = [
            ("baseline", request["baseline"]["baseline_id"]),
            *[("candidate", item["candidate_id"]) for item in request["candidates"]],
        ]
        critiques = []
        for position, (target_type, target_id) in enumerate(targets):
            dimensions = []
            for dimension in sorted(EVALUATION_DIMENSIONS):
                status = "mixed"
                unknowns = []
                blockers = []
                if self.scenario == "go":
                    status = "strong" if target_type == "baseline" else "mixed"
                elif self.scenario == "modify":
                    if target_type == "candidate" and position == 1 and dimension in {
                        "problem_evidence",
                        "buyer_economics",
                    }:
                        status = "strong"
                elif self.scenario == "hold":
                    if target_type == "baseline" and dimension == "buyer_economics":
                        status = "unknown"
                        unknowns = ["Buyer willingness to pay remains unvalidated"]
                elif self.scenario == "kill":
                    status = "weak"
                    if dimension == "technical_feasibility":
                        blockers = [
                            {
                                "reason": "Evidence-backed hard technical blocker",
                                "materiality": "hard",
                                "evidence_claim_ids": [contradiction],
                                "resolvable": False,
                            }
                        ]
                dimensions.append(
                    {
                        "dimension": dimension,
                        "status": status,
                        "rationale": f"Independent rationale for {dimension}",
                        "supporting_claim_ids": [support],
                        "contradicting_claim_ids": [contradiction],
                        "material_unknowns": unknowns,
                        "blockers": blockers,
                    }
                )
            critiques.append(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "dimensions": dimensions,
                    "strongest_reason_for": "Evidence supports meaningful customer value.",
                    "strongest_reason_against": "Counter-evidence shows adoption and execution risk.",
                    "unacceptable_conditions": ["No measurable customer value"],
                    "cheapest_next_validation": "Run a narrow buyer and workflow validation pilot.",
                    "recommendation": "hold" if self.scenario == "hold" else "advance",
                }
            )
        return {"critiques": critiques}


class MalformedEvaluationProvider(FakeEvaluationProvider):
    def evaluate(self, request):
        return {"not_critiques": []}


class EvolutionRuntimeTests(unittest.TestCase):
    def run_scenario(self, scenario):
        events = []
        result = run_evolution(
            "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템",
            research_provider=FakeResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider(scenario),
            now_provider=lambda: NOW,
            event_sink=events.append,
        )
        return result, events

    def test_completed_go_path_preserves_original_and_builds_report(self):
        result, events = self.run_scenario("go")
        self.assertEqual(result["runtime"]["status"], "completed")
        self.assertEqual(result["state"]["decision"], "GO")
        self.assertIsNone(result["state"]["selected_concept_id"])
        self.assertIsNone(result["state"]["human_decision"])
        self.assertEqual(result["state"]["report_status"], "complete")
        self.assertEqual(result["decision_result"]["decision"], "GO")
        self.assertTrue(result["evidence_graph"]["records"])
        self.assertEqual(len(result["candidates"]), 4)
        self.assertEqual(result["report"], result["state"]["executive_brief"])
        self.assertEqual(events, result["runtime"]["stage_events"])
        self.assertEqual(
            [event["stage"] for event in events if event["status"] == "started"],
            [
                "capture",
                "landscape_research",
                "assumption_analysis",
                "reframing",
                "mechanism_transfer",
                "candidate_forge",
                "collision_research",
                "independent_evaluation",
                "decision",
                "report_assembly",
            ],
        )

    def test_completed_modify_path_selects_one_evolved_concept(self):
        result, _ = self.run_scenario("modify")
        self.assertEqual(result["runtime"]["status"], "completed")
        self.assertEqual(result["state"]["decision"], "MODIFY")
        self.assertIsNotNone(result["state"]["selected_concept_id"])
        selected = next(
            candidate
            for candidate in result["candidates"]
            if candidate["candidate_id"] == result["state"]["selected_concept_id"]
        )
        self.assertEqual(result["state"]["evolved_idea"], selected["one_sentence_concept"])
        self.assertIsNone(result["state"]["human_decision"])

    def test_completed_hold_is_business_uncertainty_not_runtime_failure(self):
        result, _ = self.run_scenario("hold")
        self.assertEqual(result["runtime"]["status"], "completed")
        self.assertIsNone(result["runtime"]["failure"])
        self.assertEqual(result["state"]["decision"], "HOLD")
        self.assertEqual(result["state"]["confidence"], "low")

    def test_completed_kill_requires_evidence_backed_elimination(self):
        result, _ = self.run_scenario("kill")
        self.assertEqual(result["runtime"]["status"], "completed")
        self.assertEqual(result["state"]["decision"], "KILL")
        self.assertIsNone(result["runtime"]["failure"])

    def test_provider_timeout_is_incomplete_and_never_business_verdict(self):
        result = run_evolution(
            "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템",
            research_provider=TimeoutResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        self.assertEqual(result["runtime"]["status"], "incomplete")
        self.assertEqual(result["runtime"]["failure"]["code"], "provider_timeout")
        self.assertIsNone(result["state"]["decision"])
        self.assertIsNone(result["decision_result"])

    def test_malformed_evaluator_is_incomplete_and_decision_unset(self):
        result = run_evolution(
            "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템",
            research_provider=FakeResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            evaluation_provider=MalformedEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        self.assertEqual(result["runtime"]["status"], "incomplete")
        self.assertEqual(result["runtime"]["failure"]["code"], "evaluator_unavailable")
        self.assertIsNone(result["state"]["decision"])
        self.assertIsNone(result["decision_result"])

    def test_unexpected_internal_error_is_failed_not_hold_or_kill(self):
        result = run_evolution(
            "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템",
            research_provider=FakeResearchProvider(),
            ideation_provider=BrokenIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        self.assertEqual(result["runtime"]["status"], "failed")
        self.assertEqual(result["runtime"]["failure"]["code"], "internal_contract_violation")
        self.assertIsNone(result["state"]["decision"])

    def test_provider_runs_are_audited_without_secrets(self):
        result, _ = self.run_scenario("go")
        runs = result["runtime"]["provider_runs"]
        self.assertGreaterEqual(len(runs), 8)
        serialized = repr(runs).lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("authorization", serialized)


if __name__ == "__main__":
    unittest.main()
