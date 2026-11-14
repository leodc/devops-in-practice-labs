# Reference run

Executed on 2026-11-14 with AWS Emulator 1.0.322 and Boto3 1.40.75 in a Linux aarch64 Docker container on macOS. Native Linux installation was not separately tested.

`events.jsonl` contains actual helper observations from emulator API responses, not EventBridge service logs. Identifiers and timestamps are unchanged; no AWS credentials or real customer data are present. This file contains the final successful run from its environment record through cleanup and the expected rejection of a repeated prepare with the corrected pattern. That record contains the exact `lab.py`, initial `pattern.json`, `Dockerfile`, and `requirements.txt` hashes. `rule_updated` records the repaired pattern hash.

Commands: prepare, inspect, send, diagnose, repair (expected rejection before editing), change `order.created` to `OrderCreated` in pattern.json, repair, inspect, resend, verify, cleanup. All stages passed; the unedited repair and repeated prepare with the corrected pattern correctly exited 1. Reproduce with `bash docker-lab.sh bash validate.sh`. Four unit tests in `tests/test_guards.py` separately cover publication failures and pattern guards.

PutEvents accepted the original event with zero failed entries. TestEventPattern returned false for the original rule. After repair, the created event matched and reached SQS; the cancellation control did not match. A bounded queue observation found no control delivery; the deterministic filtering check is TestEventPattern, not the absence of a queued message.

Learner runs write to `.lab/events.jsonl` on the host. Cleanup preserves those logs.
