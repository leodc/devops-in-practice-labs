# EventBridge: accepted, but never delivered

Find why a rule excludes your event, fix the pattern, and verify delivery to SQS.

PutEvents returns without errors, but the event never reaches the queue. Reproduce the problem, compare the event with its rule, and fix the pattern before publishing again.

## Set up your environment

### 1. Clone the repository

If you already have the repository, run git pull from its root and enter this lab directory.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/eventbridge-missing-event
```

### Linux

#### 2. Start the emulator

Install AWS Emulator 1.0.322, Python with pip and venv, and nano. Then prepare the environment and start the emulator.

[Install AWS Emulator 1.0.322](https://docs.aws.amazon.com/emulator/latest/userguide/versioning.html)

**Terminal A · emulator**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
aws-emulator --version
bash start-emulator.sh
```

- Leave this terminal running.

#### 3. Open your working terminal

In a second terminal, enter the lab directory and activate its Python environment. Adjust the path to your clone.

**Terminal B · practice**

```bash
cd devops-in-practice-labs/eventbridge-missing-event
source .venv/bin/activate
```

Continue in terminal B when the emulator is ready.

### Docker

#### 2. Open the lab environment

The container includes AWS Emulator 1.0.322, Python, and nano. Logs stay in .lab on your computer.

**Your terminal → container shell**

```bash
bash docker-lab.sh
```

- Use Bash and Linux containers; on Windows, run the commands in WSL.

Continue in the shell that opens.

## 1. Inspect the rule before sending

Create an event bus, a rule, and its SQS target.

```bash
python lab.py prepare
python lab.py inspect
```

- Find detail-type in the deployed pattern. Open pattern.json and lab.py to compare the rule with the event built by event().

Does the rule select the event the publisher sends?

The rule expects order.created. The publisher sends OrderCreated. EventBridge string matching is exact.

## 2. Publish the event

Send OrderCreated and inspect the response.

```bash
python lab.py send
python lab.py inspect
```

- Find failed_entry_count: 0 and the returned EventId. Keep the correlation_id to follow this publication.

What does a successful PutEvents response confirm?

EventBridge accepted the event. That response does not confirm that a rule matched it or that a target received it.

### Reference trace

```text
{"correlation_id": "91cc5151f0654b5aa44251e659c99b99", "detail_type": "OrderCreated", "entries": [{"EventId": "18e7e097-cf5c-b28f-0000-000000000001"}], "event": "published", "failed_entry_count": 0, "time": "2026-11-14T09:51:59.155110+00:00"}
{"correlation_id": "a9950d6f3e3d448f915533bd31b80402", "detail_type": "OrderCreated", "entries": [{"EventId": "18e7e097-fc9c-993d-0000-000000000002"}], "event": "published", "failed_entry_count": 0, "time": "2026-11-14T09:51:59.915583+00:00"}
{"correlation_id": "f9f0d88007ef4917a3ed022f17532389", "detail_type": "OrderCancelled", "entries": [{"EventId": "18e7e097-fcda-0462-0000-000000000003"}], "event": "published", "failed_entry_count": 0, "time": "2026-11-14T09:51:59.917511+00:00"}
```

## 3. Test the deployed pattern

Compare the original event with the current rule using TestEventPattern.

```bash
python lab.py diagnose
```

- Find matched: false. Compare event_detail_type with the pattern in the same record.

Why is this stronger evidence than an empty queue?

An empty receive may mean delivery has not happened yet. TestEventPattern checks whether the event matches the rule’s pattern.

### Reference trace

```text
{"correlation_id": "91cc5151f0654b5aa44251e659c99b99", "event": "pattern_diagnosis", "event_detail_type": "OrderCreated", "matched": false, "pattern": {"detail-type": ["order.created"], "source": ["practice.orders"]}, "time": "2026-11-14T09:51:59.316009+00:00"}
```

## 4. Fix the event type

In pattern.json, replace order.created with OrderCreated. Save with Ctrl+O, Enter, then exit with Ctrl+X. Run repair to apply it.

```bash
nano pattern.json
python lab.py repair
python lab.py inspect
```

- Check positive_matches: true and negative_matches: false. Confirm the deployed pattern contains OrderCreated.

Why test a cancellation event too?

A pattern that matches everything would deliver the desired event while also accepting unwanted events. The helper requires OrderCreated to match and OrderCancelled to be excluded before updating the rule.

## 5. Send a fresh event and a control

Publish another OrderCreated and an OrderCancelled control, each with a new correlation ID.

```bash
python lab.py resend
```

- Find two accepted publications with distinct correlation_id values.

Will correcting the rule recover the original event?

Changing a rule does not replay earlier events. This stage sends a new event deliberately, so its ID differs from the original publication.

## 6. Follow the event into SQS

Wait for the created event, then compare its correlation ID with the publication.

```bash
python lab.py verify
```

- Find queue_delivery for OrderCreated and the matching correlation_id. Verify positive_pattern_match is true and negative_pattern_match is false.

What establishes that the control is excluded?

TestEventPattern confirms that the deployed rule excludes OrderCancelled. An empty queue during a short observation would not establish that on its own.

The helper polls for up to 30 seconds and deletes messages after recording them. If delivery is delayed, run verify again.

### Reference trace

```text
{"correlation_id": "a9950d6f3e3d448f915533bd31b80402", "event": "verification", "negative_delivery_observed": false, "negative_pattern_match": false, "observation": "bounded; negative filtering established by TestEventPattern", "positive_delivered": true, "positive_pattern_match": true, "time": "2026-11-14T09:52:03.113737+00:00"}
```

## 7. Keep the evidence, remove the resources

Delete the target, rule, bus, and queue.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Find cleanup and follow the correlation_id values from published to queue_delivery.
- Linux: stop terminal A with Ctrl+C. Docker: exit the shell. The files in .lab remain on your computer.
- If you restarted the emulator mid-lab, run python lab.py reset with the new emulator running. Restore detail-type to order.created in pattern.json before running prepare again. Earlier logs are kept.

Where did delivery stop?

The publisher succeeded, but the event did not match the rule. The corrected pattern and a new publication completed the flow.

## Publication and delivery checked

You checked event acceptance, pattern matching, and SQS delivery separately.

## References

- [EventBridge event patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-pattern.html)
- [PutEvents API](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutEvents.html)
- [AWS Emulator fidelity](https://docs.aws.amazon.com/emulator/latest/userguide/fidelity.html)
