import unittest

from src.idea_vending.bridge_store import BridgeStore


IDEA = "고객의 반복 문서업무를 예방적으로 자동화하는 운영 시스템"
TRUSTED_FORGE = {"trusted": "forge"}
COMPLETED = {"trusted": "decision"}


class Clock:
    def __init__(self):
        self.value = 100.0

    def now(self):
        return self.value


class BridgeStoreTests(unittest.TestCase):
    def test_create_uses_unpredictable_prefixed_id_and_defensive_copy(self):
        store = BridgeStore()
        first = store.create(IDEA)
        second = store.create(IDEA)
        self.assertRegex(first["bridge_session_id"], r"^br_[A-Za-z0-9_-]{16,}$")
        self.assertNotEqual(first["bridge_session_id"], second["bridge_session_id"])
        self.assertEqual(first["state"], "forge_requested")
        first["raw_idea"] = "mutated"
        self.assertEqual(store.get(first["bridge_session_id"])["raw_idea"], IDEA)

    def test_forge_replay_is_idempotent_but_conflict_is_rejected(self):
        store = BridgeStore()
        session = store.create(IDEA)["bridge_session_id"]
        first = store.save_forge(session, "digest-a", TRUSTED_FORGE)
        replay = store.save_forge(session, "digest-a", TRUSTED_FORGE)
        self.assertEqual(first, replay)
        self.assertEqual(replay["state"], "forge_validated")
        with self.assertRaisesRegex(ValueError, "conflicting_forge_replay"):
            store.save_forge(session, "digest-b", TRUSTED_FORGE)

    def test_judge_request_requires_validated_forge(self):
        store = BridgeStore()
        session = store.create(IDEA)["bridge_session_id"]
        with self.assertRaisesRegex(ValueError, "bridge_state_invalid"):
            store.mark_judge_requested(session)
        store.save_forge(session, "digest-a", TRUSTED_FORGE)
        record = store.mark_judge_requested(session)
        self.assertEqual(record["state"], "judge_requested")

    def test_decision_replay_is_idempotent_and_conflict_is_rejected(self):
        store = BridgeStore()
        session = store.create(IDEA)["bridge_session_id"]
        store.save_forge(session, "forge", TRUSTED_FORGE)
        store.mark_judge_requested(session)
        first = store.save_decision(session, "judge-a", COMPLETED)
        replay = store.save_decision(session, "judge-a", COMPLETED)
        self.assertEqual(first, replay)
        self.assertEqual(replay["state"], "decision_ready")
        with self.assertRaisesRegex(ValueError, "conflicting_judge_replay"):
            store.save_decision(session, "judge-b", COMPLETED)

    def test_ttl_and_capacity_are_bounded(self):
        clock = Clock()
        store = BridgeStore(max_entries=2, ttl_seconds=10, clock=clock.now)
        first = store.create(IDEA)["bridge_session_id"]
        second = store.create(IDEA + " 두번째")["bridge_session_id"]
        third = store.create(IDEA + " 세번째")["bridge_session_id"]
        self.assertIsNone(store.get(first))
        self.assertIsNotNone(store.get(second))
        self.assertIsNotNone(store.get(third))
        clock.value += 11
        self.assertIsNone(store.get(second))
        self.assertIsNone(store.get(third))

    def test_constructor_rejects_invalid_bounds(self):
        for kwargs in (
            {"max_entries": 0},
            {"ttl_seconds": 0},
            {"max_entries": True},
            {"clock": None},
        ):
            with self.assertRaises(ValueError):
                BridgeStore(**kwargs)


if __name__ == "__main__":
    unittest.main()
