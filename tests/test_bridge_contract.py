import math
import unittest

from src.idea_vending.bridge_contract import (
    BRIDGE_VERSION,
    MAX_BRIDGE_COLLECTION_ITEMS,
    MAX_BRIDGE_JSON_DEPTH,
    MAX_BRIDGE_STRING_CHARS,
    validate_bridge_envelope,
    validate_bridge_json,
)


class BridgeContractTests(unittest.TestCase):
    def test_version_is_fixed(self):
        self.assertEqual(BRIDGE_VERSION, "ivm-bridge-v1")

    def test_json_rejects_excessive_depth(self):
        value = "leaf"
        for _ in range(MAX_BRIDGE_JSON_DEPTH + 1):
            value = [value]
        with self.assertRaisesRegex(ValueError, "bridge_json_too_deep"):
            validate_bridge_json(value)

    def test_json_rejects_oversized_collection(self):
        with self.assertRaisesRegex(ValueError, "bridge_collection_too_large"):
            validate_bridge_json([0] * (MAX_BRIDGE_COLLECTION_ITEMS + 1))

    def test_json_rejects_oversized_string_and_non_json_type(self):
        with self.assertRaisesRegex(ValueError, "bridge_string_too_long"):
            validate_bridge_json("x" * (MAX_BRIDGE_STRING_CHARS + 1))
        with self.assertRaisesRegex(ValueError, "bridge_json_type_invalid"):
            validate_bridge_json({"unsafe": object()})

    def test_json_rejects_non_finite_numbers(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "bridge_number_invalid"):
                    validate_bridge_json({"value": value})

    def test_envelope_has_exact_keys_and_matching_version(self):
        envelope = {
            "bridge_session_id": "br_abcdefghijklmnop",
            "bridge_version": BRIDGE_VERSION,
            "result": {"ok": True},
        }
        validate_bridge_envelope(envelope)
        for mutated in (
            {**envelope, "decision": "GO"},
            {**envelope, "bridge_version": "future"},
            {**envelope, "bridge_session_id": ""},
        ):
            with self.assertRaises(ValueError):
                validate_bridge_envelope(mutated)


if __name__ == "__main__":
    unittest.main()
