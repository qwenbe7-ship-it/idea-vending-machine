import copy
import unittest

from src.idea_vending.runtime_schema import (
    append_stage_event,
    create_runtime_record,
    mark_runtime_completed,
    mark_runtime_failed,
    mark_runtime_incomplete,
    record_provider_run,
    validate_runtime_record,
)


class RuntimeSchemaTests(unittest.TestCase):
    def make_runtime(self):
        return create_runtime_record(
            "run_runtime001",
            "evo_runtime001",
            "2026-09-16T05:30:00+00:00",
        )

    def test_new_runtime_has_exact_operational_keys(self):
        runtime = self.make_runtime()
        self.assertEqual(
            set(runtime),
            {
                "runtime_id",
                "evolution_id",
                "status",
                "current_stage",
                "stage_events",
                "provider_runs",
                "failure",
                "started_at",
                "completed_at",
            },
        )
        self.assertEqual(runtime["status"], "pending")
        self.assertIsNone(runtime["current_stage"])
        self.assertEqual(runtime["stage_events"], [])
        self.assertEqual(runtime["provider_runs"], [])
        self.assertIsNone(runtime["failure"])
        self.assertIsNone(runtime["completed_at"])

    def test_stage_events_are_monotonic_and_closed_vocabulary(self):
        runtime = self.make_runtime()
        append_stage_event(
            runtime,
            stage="capture",
            status="started",
            message_code="capture_started",
            occurred_at="2026-09-16T05:30:01+00:00",
        )
        append_stage_event(
            runtime,
            stage="capture",
            status="completed",
            message_code="capture_completed",
            occurred_at="2026-09-16T05:30:02+00:00",
        )
        self.assertEqual([event["sequence"] for event in runtime["stage_events"]], [1, 2])
        self.assertEqual(runtime["current_stage"], "capture")
        self.assertEqual(runtime["status"], "running")
        with self.assertRaisesRegex(ValueError, "stage"):
            append_stage_event(
                runtime,
                stage="invented_stage",
                status="started",
                message_code="bad",
                occurred_at="2026-09-16T05:30:03+00:00",
            )
        with self.assertRaisesRegex(ValueError, "event status"):
            append_stage_event(
                runtime,
                stage="capture",
                status="pretending",
                message_code="bad",
                occurred_at="2026-09-16T05:30:03+00:00",
            )

    def test_provider_run_is_defensively_copied_and_rejects_secret_fields(self):
        runtime = self.make_runtime()
        provider_run = {
            "provider": "openai",
            "provider_response_id": "resp_123",
            "role": "research",
            "model": "gpt-5.6-terra",
            "operation": "landscape",
            "started_at": "2026-09-16T05:30:01+00:00",
            "completed_at": "2026-09-16T05:30:02+00:00",
            "status": "completed",
            "usage": {"input_tokens": 12, "output_tokens": 34},
            "source_count": 3,
        }
        record_provider_run(runtime, provider_run)
        provider_run["model"] = "tampered"
        self.assertEqual(runtime["provider_runs"][0]["model"], "gpt-5.6-terra")

        unsafe = copy.deepcopy(runtime["provider_runs"][0])
        unsafe["api_key"] = "secret"
        with self.assertRaisesRegex(ValueError, "provider run"):
            record_provider_run(runtime, unsafe)

    def test_incomplete_has_failure_and_completion_time_but_no_business_fields(self):
        runtime = self.make_runtime()
        mark_runtime_incomplete(
            runtime,
            code="provider_timeout",
            stage="landscape_research",
            occurred_at="2026-09-16T05:31:00+00:00",
        )
        self.assertEqual(runtime["status"], "incomplete")
        self.assertEqual(runtime["failure"]["code"], "provider_timeout")
        self.assertEqual(runtime["completed_at"], "2026-09-16T05:31:00+00:00")
        self.assertNotIn("decision", runtime)
        validate_runtime_record(runtime)

    def test_failed_is_reserved_for_internal_contract_failure(self):
        runtime = self.make_runtime()
        mark_runtime_failed(
            runtime,
            code="internal_contract_violation",
            stage="decision",
            occurred_at="2026-09-16T05:31:00+00:00",
        )
        self.assertEqual(runtime["status"], "failed")
        self.assertEqual(runtime["failure"]["code"], "internal_contract_violation")
        validate_runtime_record(runtime)

    def test_completed_runtime_requires_no_failure(self):
        runtime = self.make_runtime()
        append_stage_event(
            runtime,
            stage="report_assembly",
            status="completed",
            message_code="report_assembly_completed",
            occurred_at="2026-09-16T05:31:00+00:00",
        )
        mark_runtime_completed(runtime, occurred_at="2026-09-16T05:31:01+00:00")
        self.assertEqual(runtime["status"], "completed")
        self.assertIsNone(runtime["failure"])
        self.assertEqual(runtime["completed_at"], "2026-09-16T05:31:01+00:00")
        validate_runtime_record(runtime)

    def test_invalid_runtime_or_evolution_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "runtime_id"):
            create_runtime_record("bad", "evo_runtime001", "2026-09-16T05:30:00+00:00")
        with self.assertRaisesRegex(ValueError, "evolution_id"):
            create_runtime_record("run_runtime001", "bad", "2026-09-16T05:30:00+00:00")


if __name__ == "__main__":
    unittest.main()
