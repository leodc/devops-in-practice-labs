"""Guard regressions; the separate reference recording exercises real APIs."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("practice_lab", Path(__file__).resolve().parents[1] / "lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class GuardTests(unittest.TestCase):
    def make_lab(self):
        instance = lab.Lab.__new__(lab.Lab)
        instance.state = {"phase": "diagnosed", "bus": "test-bus", "rule": "orders", "original": {"detail-type": "OrderCreated"}}
        instance.events = Mock()
        return instance

    @patch.object(lab, "emit")
    def test_partial_publication_failure_is_not_success(self, emit):
        instance = self.make_lab()
        instance.events.put_events.return_value = {"FailedEntryCount": 1, "Entries": [{"ErrorCode": "InternalFailure"}]}
        with self.assertRaisesRegex(RuntimeError, "PutEvents failed"):
            instance.publish(instance.event("test-correlation"))
        self.assertEqual(emit.call_args.kwargs["failed_entry_count"], 1)

    @patch.object(lab, "emit")
    def test_broad_pattern_is_rejected_before_mutation(self, emit):
        instance = self.make_lab()
        instance.events.test_event_pattern.return_value = {"Result": True}
        with self.assertRaisesRegex(RuntimeError, "reject OrderCancelled"):
            instance.repair()
        instance.events.put_rule.assert_not_called()
        self.assertEqual(instance.state["phase"], "diagnosed")

    @patch.object(lab, "emit")
    def test_unfixed_pattern_is_rejected_before_mutation(self, emit):
        instance = self.make_lab()
        instance.events.test_event_pattern.return_value = {"Result": False}
        with self.assertRaisesRegex(RuntimeError, "match OrderCreated"):
            instance.repair()
        instance.events.put_rule.assert_not_called()

    def test_corrected_starting_pattern_is_rejected_before_resources(self):
        instance = self.make_lab()
        instance.state = {}
        instance.events.test_event_pattern.return_value = {"Result": True}
        with self.assertRaisesRegex(RuntimeError, "Restore pattern.json"):
            instance.prepare()
        instance.events.create_event_bus.assert_not_called()
        self.assertEqual(instance.state, {})


if __name__ == "__main__":
    unittest.main()
