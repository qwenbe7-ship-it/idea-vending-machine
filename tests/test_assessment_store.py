from copy import deepcopy
import threading
import unittest

from src.idea_vending.assessment_store import AssessmentStore
from src.idea_vending.evolution_runtime import run_evolution
from tests.test_evolution_runtime import (
    FakeEvaluationProvider,
    FakeIdeationProvider,
    FakeResearchProvider,
    NOW,
    TimeoutResearchProvider,
)


class FakeClock:
    def __init__(self, value=100.0):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


def completed_result(label="base"):
    return run_evolution(
        f"고객 운영 반복업무를 예방 자동화하는 검증 시스템 {label}",
        research_provider=FakeResearchProvider(),
        ideation_provider=FakeIdeationProvider(),
        evaluation_provider=FakeEvaluationProvider("go"),
        now_provider=lambda: NOW,
    )


def incomplete_result():
    return run_evolution(
        "고객 운영 반복업무를 예방 자동화하는 미완료 시스템",
        research_provider=TimeoutResearchProvider(),
        ideation_provider=FakeIdeationProvider(),
        evaluation_provider=FakeEvaluationProvider("go"),
        now_provider=lambda: NOW,
    )


class AssessmentStoreTests(unittest.TestCase):
    def test_store_has_reentrant_lock_for_threading_http_server(self):
        store = AssessmentStore()
        self.assertIsInstance(store._lock, type(threading.RLock()))

    def test_save_completed_returns_trusted_runtime_id_and_unapproved_record(self):
        clock = FakeClock()
        store = AssessmentStore(max_entries=2, ttl_seconds=10, clock=clock)
        result = completed_result()

        runtime_id = store.save_completed(result)
        record = store.get(runtime_id)

        self.assertEqual(runtime_id, result["runtime"]["runtime_id"])
        self.assertEqual(record["runtime_id"], runtime_id)
        self.assertEqual(record["evolution_id"], result["runtime"]["evolution_id"])
        self.assertFalse(record["approved"])
        self.assertIsNone(record["documents"])
        self.assertIsNone(record["approved_state"])

    def test_incomplete_result_cannot_be_stored(self):
        store = AssessmentStore()
        result = incomplete_result()
        self.assertEqual(result["runtime"]["status"], "incomplete")

        with self.assertRaisesRegex(ValueError, "completed"):
            store.save_completed(result)

    def test_get_returns_defensive_copy(self):
        store = AssessmentStore()
        result = completed_result()
        runtime_id = store.save_completed(result)

        record = store.get(runtime_id)
        record["result"]["state"]["decision"] = "KILL"

        self.assertNotEqual(store.get(runtime_id)["result"]["state"]["decision"], "KILL")

    def test_expired_record_is_removed(self):
        clock = FakeClock()
        store = AssessmentStore(max_entries=2, ttl_seconds=10, clock=clock)
        runtime_id = store.save_completed(completed_result())

        clock.advance(11)

        self.assertIsNone(store.get(runtime_id))

    def test_capacity_evicts_oldest_record(self):
        clock = FakeClock()
        store = AssessmentStore(max_entries=2, ttl_seconds=100, clock=clock)
        ids = []
        for label in ("one", "two", "three"):
            ids.append(store.save_completed(completed_result(label)))
            clock.advance(1)

        self.assertIsNone(store.get(ids[0]))
        self.assertIsNotNone(store.get(ids[1]))
        self.assertIsNotNone(store.get(ids[2]))

    def test_mark_approved_persists_defensive_state_and_deterministic_documents(self):
        store = AssessmentStore()
        result = completed_result()
        runtime_id = store.save_completed(result)
        state = deepcopy(result["state"])
        state["human_decision"] = "proceed"
        documents = {
            "spec.md": "spec v1",
            "design.md": "design v1",
            "plan.md": "plan v1",
        }

        first = store.mark_approved(runtime_id, state, documents)
        state["decision"] = "KILL"
        documents["spec.md"] = "tampered"
        second = store.mark_approved(
            runtime_id,
            state,
            {"spec.md": "divergent", "design.md": "divergent", "plan.md": "divergent"},
        )

        self.assertTrue(first["approved"])
        self.assertEqual(first["approved_state"]["human_decision"], "proceed")
        self.assertEqual(first["documents"]["spec.md"], "spec v1")
        self.assertEqual(second["documents"], first["documents"])
        self.assertNotEqual(second["approved_state"]["decision"], "KILL")

    def test_idempotent_resave_does_not_clear_existing_approval(self):
        store = AssessmentStore()
        result = completed_result("idempotent")
        runtime_id = store.save_completed(result)
        state = deepcopy(result["state"])
        state["human_decision"] = "proceed"
        documents = {"spec.md": "spec", "design.md": "design", "plan.md": "plan"}
        store.mark_approved(runtime_id, state, documents)

        returned_id = store.save_completed(deepcopy(result))
        record = store.get(runtime_id)

        self.assertEqual(returned_id, runtime_id)
        self.assertTrue(record["approved"])
        self.assertEqual(record["documents"], documents)

    def test_same_runtime_id_with_different_result_is_rejected(self):
        store = AssessmentStore()
        result = completed_result("collision")
        runtime_id = store.save_completed(result)
        mutated = deepcopy(result)
        mutated["report"] = {"thesis": "different top-level result with same trusted runtime id"}

        with self.assertRaisesRegex(ValueError, "runtime_id collision"):
            store.save_completed(mutated)

        self.assertEqual(store.get(runtime_id)["result"], result)

    def test_constructor_rejects_nonpositive_capacity_or_ttl(self):
        with self.assertRaises(ValueError):
            AssessmentStore(max_entries=0)
        with self.assertRaises(ValueError):
            AssessmentStore(ttl_seconds=0)


if __name__ == "__main__":
    unittest.main()
