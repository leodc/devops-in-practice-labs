# DynamoDB: two writes, one lost update

Reproduce a lost increment, reject a stale write, and retry with fresh data.

Two writers read the same counter and both writes succeed. Yet the value increases only once. Reproduce the sequence with AWS Emulator, add a version condition, and work through the rejected writer’s retry.

## Set up your environment

### 1. Clone the repository

If you already have the repository, run git pull from its root and enter this lab directory.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/dynamodb-lost-update
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
cd devops-in-practice-labs/dynamodb-lost-update
source .venv/bin/activate
```

Continue in terminal B when the emulator is ready.

### Docker

#### 2. Enter the lab environment

The container includes AWS Emulator 1.0.322, Python, and nano. Logs stay in .lab on your computer.

**Your terminal → container shell**

```bash
bash docker-lab.sh
```

- On Windows, run these commands in WSL with Docker using Linux containers.

Continue in the shell that opens.

## 1. Create the counter

Create a table with a counter at value 0 and version 0.

```bash
python lab.py prepare
python lab.py inspect
```

- Find status ACTIVE and applied_writer.check_version set to false.
- Open lab.py and find write: it calculates the next value from a saved snapshot.

Does a successful write prove that no other update was lost?

UpdateItem accepts a replacement value unless a condition rejects it. Success alone says nothing about the snapshot used to calculate that value.

## 2. Make both writers use the same snapshot

Read the counter twice, then write A followed by B. Both calculate 0 + 1.

```bash
python lab.py collide
python lab.py inspect
```

- Find snapshots_read with two value 0 snapshots, then two write_accepted events with value 1.

Why did two accepted increments leave the value at 1?

B overwrote A’s result with the same calculated value. The script runs the reads and writes in a fixed order to reproduce a problem concurrent writers can cause.

Both reads are strongly consistent. That makes each read current when it happens; it does not reserve the item until a later write.

## 3. Find the lost increment

Compare the accepted writes with the stored value.

```bash
python lab.py diagnose
```

- Find lost_update: accepted_writes is 2, but observed.value is 1.

Could strongly consistent reads alone prevent this overwrite?

A writer can still act on a stale value after another writer changes it. The write itself must check that the version it read is still current.

### Reference trace

```text
{"accepted_writes": 2, "cause": "Both writers calculated 0 + 1 before either write.", "event": "lost_update", "expected_value": 2, "observed": {"value": 1, "version": 1}, "time": "2026-11-14T09:47:11.502727+00:00"}
```

## 4. Require the version you read

Change check_version to true in writer.json. Save with Ctrl+O, Enter; exit with Ctrl+X. Apply the configuration.

```bash
nano writer.json
python lab.py repair
python lab.py inspect
```

- Check that file_writer and applied_writer both show check_version true.

Where does this condition run?

The helper adds ConditionExpression to UpdateItem. DynamoDB checks the version atomically with the write. This flag configures the lab’s writer, not the table.

## 5. Reject the stale write

Reset the counter to 0 and repeat the same two snapshots with version checks enabled. This starts a comparison run; it does not restore the lost increment.

```bash
python lab.py replay
python lab.py inspect
```

- A succeeds. B receives ConditionalCheckFailedException because its version 0 no longer matches version 1.

Has the condition completed both increments?

It prevented an overwrite. B’s increment is still pending. Repeating B’s old request would fail the same condition.

### Reference trace

```text
{"check_version": true, "code": "ConditionalCheckFailedException", "event": "write_rejected", "observed": {"value": 1, "version": 1}, "snapshot": {"value": 0, "version": 0}, "time": "2026-11-14T09:47:12.253195+00:00", "writer": "B"}
```

## 6. Read again, then recalculate

Refresh B’s snapshot and calculate its increment from the current value.

```bash
python lab.py retry
python lab.py inspect
```

- Follow snapshot_refreshed from version 0 to 1, then write_accepted with value 2 and version 2.

What changed between the rejected request and this retry?

B read the current item and recalculated both its new value and its expected version. The helper retries once; an application needs to decide how many conflicts to retry before stopping.

## 7. Check that both increments survived

Read the final counter and check the applied writer configuration.

```bash
python lab.py verify
```

- Find verification with result PASS, value 2, and version 2.

Is optimistic locking the only way to increment a counter?

A simple counter can use an atomic UpdateItem increment. Here, the version condition protects a decision based on an earlier read.

### Reference trace

```text
{"event": "verification", "increments": 2, "observed": {"value": 2, "version": 2}, "result": "PASS", "time": "2026-11-14T09:47:12.928307+00:00"}
```

## 8. Keep the evidence, remove the table

Delete the table. The sequence remains in .lab/events.jsonl on your computer.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Find cleanup_completed. Stop the emulator terminal on Linux, or exit the Docker shell.
- If the emulator restarted mid-lab, run python lab.py reset. Set check_version to false before preparing a new run. Logs are retained.

Which events distinguish a lost update from a rejected write?

Compare the two unprotected write_accepted events with write_rejected, snapshot_refreshed, and the final verification. These are helper logs of actual API outcomes.

Share events.jsonl; the emulator startup log can contain generated local credentials.

## Explain the retry

Use your logs to show why a consistent read did not prevent the lost update, what the condition rejected, and why the next attempt succeeded.

## References

- [AWS Emulator · installation](https://docs.aws.amazon.com/emulator/latest/userguide/setting-up.html)
- [DynamoDB · optimistic locking](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBMapper.OptimisticLocking.html)
- [DynamoDB · update expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html)
