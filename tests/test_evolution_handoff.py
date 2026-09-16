import unittest

from src.idea_vending.evolution_handoff import (
    can_handoff_to_development,
    generate_approved_development_package,
)
from tests.test_evolution_schema import make_complete_state


class EvolutionHandoffTests(unittest.TestCase):
    def test_hold_is_blocked(self):
        state = make_complete_state()
        state["decision"] = "HOLD"
        state["human_decision"] = "hold"
        self.assertFalse(can_handoff_to_development(state))
        with self.assertRaisesRegex(ValueError, "HOLD"):
            generate_approved_development_package(state)

    def test_kill_is_blocked(self):
        state = make_complete_state()
        state["decision"] = "KILL"
        state["human_decision"] = "kill"
        self.assertFalse(can_handoff_to_development(state))
        with self.assertRaisesRegex(ValueError, "KILL"):
            generate_approved_development_package(state)

    def test_handoff_requires_explicit_human_proceed(self):
        state = make_complete_state()
        state["human_decision"] = None
        self.assertFalse(can_handoff_to_development(state))
        with self.assertRaisesRegex(ValueError, "human"):
            generate_approved_development_package(state)

    def test_modify_requires_evolved_idea(self):
        state = make_complete_state()
        state["decision"] = "MODIFY"
        state["evolved_idea"] = None
        self.assertFalse(can_handoff_to_development(state))
        with self.assertRaisesRegex(ValueError, "evolved_idea"):
            generate_approved_development_package(state)

    def test_incomplete_report_is_blocked(self):
        state = make_complete_state()
        state["report_status"] = "draft"
        self.assertFalse(can_handoff_to_development(state))
        with self.assertRaisesRegex(ValueError, "complete"):
            generate_approved_development_package(state)

    def test_approved_go_can_use_original_idea(self):
        state = make_complete_state()
        state["decision"] = "GO"
        state["evolved_idea"] = None
        self.assertTrue(can_handoff_to_development(state))
        documents = generate_approved_development_package(state)
        self.assertEqual(set(documents), {"spec.md", "design.md", "plan.md"})
        self.assertIn(state["raw_idea"], documents["spec.md"])

    def test_approved_modify_uses_evolved_idea(self):
        state = make_complete_state()
        state["decision"] = "MODIFY"
        self.assertTrue(can_handoff_to_development(state))
        documents = generate_approved_development_package(state)
        self.assertEqual(set(documents), {"spec.md", "design.md", "plan.md"})
        self.assertIn(state["evolved_idea"], documents["spec.md"])


if __name__ == "__main__":
    unittest.main()
