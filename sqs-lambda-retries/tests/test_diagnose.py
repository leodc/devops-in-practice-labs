"""Regression tests for asynchronous diagnosis; no AWS/emulator calls."""

import unittest
from unittest.mock import Mock, patch

import lab


def failure(count, message_id="poison-id"):
    return {"event": "deliberate_failure", "receive_count": str(count),
            "message_id": message_id, "body": "order-poison"}


CONTROL = {"event": "processed", "body": "order-ok"}
EVIDENCE = [failure(1), failure(2), failure(3), CONTROL]
MESSAGE = {"Body": "order-poison", "MessageId": "poison-id", "ReceiptHandle": "receipt",
           "Attributes": {"ApproximateReceiveCount": "4"}}


class DiagnoseTests(unittest.TestCase):
    def setUp(self):
        self.runner = lab.Lab.__new__(lab.Lab)
        self.runner.state = {"phase": "consuming", "dlq": "local-dlq",
                             "messages": {"order-poison": "poison-id"}}
        self.runner.save = Mock()
        self.runner.sqs = Mock()
        self.runner.sqs.receive_message.return_value = {"Messages": [MESSAGE]}
        self.runner.counts = Mock(return_value={"ApproximateNumberOfMessages": 1})
        self.runner.read_logs = Mock(return_value=EVIDENCE)
        # Virtual time keeps timeout coverage fast and deterministic.
        self.now = 0
        for target, kwargs in [
            ("lab.emit", {}),
            ("lab.time.monotonic", {"side_effect": lambda: self.now}),
            ("lab.time.sleep", {"side_effect": self.advance}),
        ]:
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def advance(self, seconds):
        self.now += seconds

    def test_waits_for_queue_logs_control_and_nonempty_receive(self):
        self.runner.counts.side_effect = [
            {"ApproximateNumberOfMessages": 0}, {"ApproximateNumberOfMessages": 1}]
        self.runner.read_logs.side_effect = [[], [], [failure(1)],
            [failure(3), failure(1), failure(2)],
            [failure(3), CONTROL, failure(1), failure(2)]]
        self.runner.sqs.receive_message.side_effect = [{}, {"Messages": []}, {"Messages": [MESSAGE]}]
        self.runner.diagnose()
        self.assertEqual(self.runner.state["phase"], "diagnosed")
        self.assertEqual(self.runner.state["diagnosis"]["failed_deliveries"], 3)
        self.assertEqual(self.runner.sqs.receive_message.call_count, 3)
        self.assertEqual(self.runner.read_logs.call_count, 5)
        self.assertEqual(self.runner.sqs.receive_message.call_args.kwargs["WaitTimeSeconds"], 5)
        self.runner.sqs.change_message_visibility.assert_called_once_with(
            QueueUrl="local-dlq", ReceiptHandle="receipt", VisibilityTimeout=0)

    def test_missing_logs_timeout_keeps_stage_and_does_not_receive(self):
        self.runner.read_logs.return_value = [failure(1)]
        with self.assertRaisesRegex(TimeoutError, "three failure logs"):
            self.runner.diagnose()
        self.assertEqual(self.runner.state["phase"], "consuming")
        self.runner.sqs.receive_message.assert_not_called()

    def test_empty_receives_timeout_without_saving_diagnosis(self):
        self.runner.sqs.receive_message.return_value = {}
        with self.assertRaisesRegex(TimeoutError, "receive failed message from DLQ"):
            self.runner.diagnose()
        self.assertGreater(self.runner.sqs.receive_message.call_count, 1)
        self.assertEqual(self.runner.state["phase"], "consuming")
        self.assertNotIn("diagnosis", self.runner.state)
        self.runner.sqs.change_message_visibility.assert_not_called()

    def test_wrong_failure_identity_is_not_treated_as_delay(self):
        self.runner.read_logs.return_value = [failure(1, "other-id")]
        with self.assertRaisesRegex(RuntimeError, "Unexpected failed message"):
            self.runner.diagnose()
        self.runner.sqs.receive_message.assert_not_called()

    def test_unexpected_poison_success_is_rejected(self):
        self.runner.read_logs.return_value = EVIDENCE + [{"event": "processed", "body": "order-poison"}]
        with self.assertRaisesRegex(RuntimeError, "unexpectedly processed"):
            self.runner.diagnose()
        self.runner.sqs.receive_message.assert_not_called()

    def test_invalid_dlq_message_is_released_without_advancing(self):
        self.runner.sqs.receive_message.return_value = {"Messages": [{**MESSAGE, "Body": "other"}]}
        with self.assertRaisesRegex(RuntimeError, "Unexpected DLQ message"):
            self.runner.diagnose()
        self.assertEqual(self.runner.state["phase"], "consuming")
        self.runner.sqs.change_message_visibility.assert_called_once_with(
            QueueUrl="local-dlq", ReceiptHandle="receipt", VisibilityTimeout=0)

    def test_repeat_diagnose_uses_saved_evidence_without_receiving_again(self):
        self.runner.diagnose()
        self.runner.sqs.reset_mock()
        self.runner.read_logs.reset_mock()
        self.runner.diagnose()
        self.runner.sqs.receive_message.assert_not_called()
        self.runner.read_logs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
