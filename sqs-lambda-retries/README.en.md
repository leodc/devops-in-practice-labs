# SQS + Lambda: break the flow, recover the message

Make Lambda fail, trace SQS retries, and recover a message from the DLQ. Our first local lab: real code, real logs, no AWS account required.

A message keeps failing and ends up in a dead-letter queue (DLQ). Reproduce that failure with AWS Emulator, find the cause in the logs, and recover the message after fixing the consumer.

## Set up your environment

### 1. Clone the repository

Run the rest of the commands from this lab directory.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-lambda-retries
```

### Linux

#### 2. Start the emulator

Install AWS Emulator 1.0.322 and Python with pip and venv. Then prepare the Python environment and start the emulator.

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

In a second terminal, enter the lab directory and activate its Python environment. Adjust the path if you cloned the repository elsewhere.

**Terminal B · practice**

```bash
cd devops-in-practice-labs/sqs-lambda-retries
source .venv/bin/activate
```

Once the emulator is ready, continue in terminal B.

### Docker

#### 2. Enter the lab environment

The image includes AWS Emulator 1.0.322, Python, and nano. Build it from the lab directory and open its shell.

**Your terminal → container shell**

```bash
docker build -t sqs-lambda-practice .
docker run --rm -it --name sqs-lambda-practice --network none --memory=2g --memory-swap=2g sqs-lambda-practice
```

- Docker must be running Linux containers.

The shell opens when the emulator is ready. Continue there.

## 1. Create the queues and function

Create the source queue, DLQ, and Lambda function. Leave the event source mapping disabled so you can inspect them before processing messages.

```bash
python lab.py prepare
python lab.py inspect
```

- Check that the mapping is Disabled, fail_poison is true, and both queues are empty.
- Open handler.py and find what makes order-poison fail. The lab uses one record per invocation, a 1-second function timeout, a 6-second visibility timeout, and maxReceiveCount 3.

What does the disabled mapping let you inspect?

You can check the function and queues before polling starts. Sending messages will not trigger processing until you enable the mapping.

These settings keep the exercise short. AWS recommends a visibility timeout at least six times the function timeout and maxReceiveCount of at least five; this lab uses three to reach the DLQ sooner.

## 2. Send two messages

Send order-ok and order-poison while consumption is still disabled.

```bash
python lab.py send
python lab.py inspect
```

- Find the two sent events and save the message_id for order-poison.
- Check for two visible messages in the source queue and an empty DLQ.

Why are there no handler logs yet?

The event source mapping polls SQS and invokes Lambda. While it is disabled, both messages remain in the queue.

## 3. Start processing

Enable the mapping. Lambda will process the messages and retries will continue in the background.

```bash
python lab.py consume
python lab.py inspect
```

- Look for processed for order-ok and deliberate_failure for order-poison. Run inspect again if the logs have not arrived.
- Follow message_id and receive_count across attempts.

What lets the failed message become available again?

The handler raises an error for order-poison, so the message stays in SQS. When its visibility timeout expires, it becomes available for another attempt.

With one record per invocation, the successful message is not retried alongside the failing one.

## 4. Inspect retries and the DLQ

Wait for the message to reach the DLQ and inspect its logs and metadata.

```bash
python lab.py diagnose
python lab.py inspect
```

- Find three deliberate_failure events for the same message, with receive_count 1, 2, and 3: one initial attempt and two retries.
- Find the diagnosis event for order-poison. Compare its dlq_receive_count with the failure logs.

Does a receive count of 4 prove that Lambda failed four times?

Lambda failed three times. The fourth receive was the diagnostic read from the DLQ. The script restores the message’s visibility immediately; repeating diagnose returns the saved result without receiving it again.

The source queue’s redrive policy sends the message to this DLQ. This is separate from Lambda’s DLQ configuration for asynchronous invocations.

```text
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "1"}
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "2"}
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "3"}
{"body": "order-poison", "dlq_receive_count": "4", "event": "diagnosis", "failed_deliveries": 3, "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "time": "2026-11-12T02:37:23.550458+00:00"}
```

## 5. Fix the consumer

In consumer.json, change fail_poison to false. Save in nano with Ctrl+O, Enter, then exit with Ctrl+X. Run repair to apply the change to Lambda.

```bash
nano consumer.json
python lab.py repair
python lab.py inspect
```

- Check that the function reports fail_poison as false.
- Confirm the message is still in the DLQ.

Why has the fixed function not processed that message yet?

The mapping polls the source queue, but the message is in the DLQ. Fixing the function does not return it to the source queue.

## 6. Return the message to the source queue

Start a redrive task. The mapping is still enabled, so Lambda can process the message as soon as it returns.

```bash
python lab.py redrive
python lab.py inspect
```

- Find redrive_started and its task handle. This confirms that the task started; verify checks whether recovery completed.

What would happen if you redrove the message before fixing the failure?

The message would fail again. Repair the consumer before returning messages to a queue it is still polling.

## 7. Verify recovery

Check that redrive completed, Lambda processed order-poison, and both queues are empty.

```bash
python lab.py verify
python lab.py inspect
```

- Find verification with result PASS and a processed event for order-poison.
- Check redrive_identity_observed. Emulator 1.0.322 preserves the message ID and receive count; AWS assigns a new ID and enqueue time after redrive.

Why would an empty DLQ be insufficient evidence?

An empty DLQ only tells you the message left it. Successful recovery also needs a completed redrive task, a processed log, and zero visible, in-flight, or delayed messages in both queues.

```text
{"body": "order-poison", "event": "processed", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "5"}
{"dlq": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "event": "verification", "result": "PASS", "source": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "time": "2026-11-12T02:37:29.200757+00:00"}
```

## 8. Save the logs and clean up

Delete the emulated resources. Your logs remain in .lab/events.jsonl.

```bash
python lab.py cleanup
tail -n 5 .lab/events.jsonl
```

- Check for cleanup_completed.
- Linux: stop terminal A with Ctrl+C.
- Docker: before leaving the container, run docker cp sqs-lambda-practice:/opt/lab/.lab ./practice-logs from a host terminal. Then exit the container shell.
- If you restarted the emulator mid-lab, run python lab.py reset, then python lab.py prepare. Existing logs are kept; use timestamps to distinguish runs.

Which log entries explain the failure and recovery?

Follow the original message ID through the three failures, the DLQ read, the repair, and redrive. Finish with the processed event and PASS result.

Share events.jsonl rather than the raw emulator startup log, which can contain generated local credentials.

## Read the whole sequence

Use your logs to explain when the message became available again, why it reached the DLQ, and what confirms that recovery succeeded.

## References

- [AWS Emulator · requirements and installation](https://docs.aws.amazon.com/emulator/latest/userguide/setting-up.html)
- [AWS Emulator · native Linux setup](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-linux.html)
- [Lambda · configuring SQS event sources](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html)
- [Lambda · handling errors for SQS](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)
- [SQS · dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [SQS · redrive and message identity](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html)
