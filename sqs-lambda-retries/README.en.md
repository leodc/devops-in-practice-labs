# SQS + Lambda: break the flow, recover the message

Make Lambda fail, trace SQS retries, and recover a message from the DLQ. Our first local lab: real code, real logs, no AWS account required.

Your Lambda function processes one message and fails on the next. After repeated attempts, the failing message ends up in a dead-letter queue (DLQ). Your job is to find the cause, fix the consumer, and recover the message without repeating the failure.

Reproduce this scenario on your machine with AWS Emulator, without an AWS account. Work through it in stages: inspect the queues, follow the logs, and verify that the recovered message was actually processed.

## Set up your environment

### 1. Clone the repository

You need Git. Run these commands where you want to keep the lab.


```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-lambda-retries
```


### Linux

#### 2. Start the emulator

Install AWS Emulator 1.0.322 using the guide below. You’ll also need Python with pip and venv to run the lab. From the lab directory, prepare its dependencies and start the emulator.

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

Open a second terminal and enter the same repository. Adjust the cd path if you cloned it elsewhere. Run every lab stage here.

**Terminal B · practice**


```bash
cd devops-in-practice-labs/sqs-lambda-retries
source .venv/bin/activate
```


Emulator running in A and Python ready in B. Continue in terminal B.

### Docker

#### 2. Enter the lab environment

From the repository directory, build the image and open its shell. AWS Emulator 1.0.322 starts automatically; Python and nano are included.

**Your terminal → container shell**


```bash
docker build -t sqs-lambda-practice .
docker run --rm -it --name sqs-lambda-practice --network none --memory=2g --memory-swap=2g sqs-lambda-practice
```


- Use a Docker engine running Linux containers.
- Run the stages inside that shell. The container runs without external networking, published ports, or mounted AWS credentials.

Container shell open and emulator ready. Continue inside the container.

## 1. Build the experiment, with consumption disabled

Create a source queue, its dead-letter queue, a Lambda function, and a disabled event source mapping. The helper uses only the emulator’s generated credentials and an explicit loopback endpoint.


```bash
python lab.py prepare
python lab.py inspect
```


- Find mapping state Disabled, consumer fail_poison true, and empty source/DLQ counts.
- Read configuration: batch size 1, function timeout 1 second, visibility timeout 6 seconds, max_receive_count 3. Inspect handler.py before proceeding.

Why start with the mapping disabled?

It gives you a stable point to inspect the infrastructure before Lambda polls the queue. No message has been sent yet.

The short settings make failure observable in a small exercise. AWS recommends a visibility timeout at least six times the function timeout and maxReceiveCount of at least five; three is a deliberate teaching choice, not a production recommendation.

## 2. Send two messages, then stop

Send order-ok and order-poison. Sending a message should not silently start the next stage.


```bash
python lab.py send
python lab.py inspect
```


- Find two sent records with different message IDs. Keep the ID for order-poison.
- The source should show two visible messages; the mapping is still Disabled and the DLQ is empty.

Why are there no handler logs yet?

An SQS message does not invoke the function on its own. The enabled event source mapping polls SQS and invokes Lambda. We have deliberately left that mapping disabled.

Repeated send calls are rejected for this session, so accidentally copying the block twice will not enqueue another pair.

## 3. Enable consumption and watch the failure

Start polling. Retries now proceed in the background, even while you read this page. You can run inspect again at any point to retrieve new logs.


```bash
python lab.py consume
python lab.py inspect
```


- Look for received and processed for order-ok, and deliberate_failure for order-poison. If logs have not arrived, inspect again.
- Follow message_id and receive_count. Queue counters can change as the consumer works; an empty visible count alone does not mean success.

What lets the failed message become available again?

The handler raises an error for order-poison. The message is not successfully acknowledged and deleted. After its visibility timeout it can be received again.

With batch size one, the good message is not retried alongside the failing one. Larger batches and partial batch responses are a separate experiment.

## 4. Inspect the retries and the DLQ

Wait for the failed message and its logs, then inspect the DLQ message body and metadata. Each wait has a deadline, including retries when a receive returns no message; it does not repair the consumer or redrive the message.


```bash
python lab.py diagnose
python lab.py inspect
```


- Find three deliberate_failure logs for the same message, with receive_count 1, 2, and 3. That is three deliveries: the initial attempt plus two retries.
- Find a diagnosis event for order-poison, a successful order-ok log, and one visible message in the DLQ.
- The helper receives the DLQ message to inspect it, then immediately restores its visibility. That inspection itself increments the receive count.

Does a receive count of 4 prove that Lambda failed four times?

No. In the reference run, Lambda failed three times. The fourth receive was our diagnostic read from the DLQ, not another function invocation. Count the actual handler failure logs.

The source queue’s redrive policy moves the message to its DLQ. This is an SQS queue configuration, not the DLQ setting for asynchronous Lambda invocations.

Calling diagnose again returns the saved diagnosis instead of receiving the DLQ message again.

```text
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "1"}
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "2"}
{"body": "order-poison", "event": "deliberate_failure", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "3"}
{"body": "order-poison", "dlq_receive_count": "4", "event": "diagnosis", "failed_deliveries": 3, "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "time": "2026-11-12T02:37:23.550458+00:00"}
```

## 5. Fix the consumer, then inspect again

Open consumer.json and change fail_poison from true to false. In nano, save with Ctrl+O, Enter, and exit with Ctrl+X. Then apply the configuration change to the emulated function.


```bash
nano consumer.json
python lab.py repair
python lab.py inspect
```


- Confirm consumer fail_poison is false. Editing the file alone does not update the function; repair applies it.
- The DLQ should still contain one message. The function fix has not moved it back to the source queue.

Why has the fixed function not processed that message yet?

The mapping polls the source queue. The message is waiting in a different queue: the DLQ. Fixing the consumer and recovering failed messages are separate operations.

The helper rejects repair while fail_poison is still true. This makes the file edit an explicit part of the exercise.

## 6. Return the message to the source queue

Start a redrive task from the DLQ to the source queue only after inspecting the fix. The consumer remains enabled.


```bash
python lab.py redrive
python lab.py inspect
```


- Find redrive_started with a task handle. This confirms the request, not completed recovery.
- The message can already be processing by the time you inspect. Use the next stage to check the completed task, handler success, and both queues.

What would happen if you redrove the message before fixing the failure?

It would meet the same failing handler again. Redrive moves messages; it does not resolve the underlying error.

The lab’s stage guard prevents this ordering mistake. Production recovery needs the same reasoning even when the API allows the action.

## 7. Verify recovery with more than an empty queue

Wait for the redrive task to complete, a processed log for order-poison, and zero visible, in-flight, and delayed messages in both queues.


```bash
python lab.py verify
python lab.py inspect
```


- Find verification with result PASS, and the handler’s processed event for order-poison.
- Read redrive_identity_observed. In emulator 1.0.322 the ID and receive count were preserved. AWS documents new IDs and enqueue times after redrive: this is an observed fidelity gap.

Why would an empty DLQ be insufficient evidence?

A message could have moved without being processed successfully. The helper combines task completion, a successful handler log, and queue counts.

Use the emulator to study the flow, but do not turn its preserved message ID or exact retry timing into assumptions about AWS.

```text
{"body": "order-poison", "event": "processed", "message_id": "193c9481-2fae-42ae-a35a-e77fe77c20e5", "receive_count": "5"}
{"dlq": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "event": "verification", "result": "PASS", "source": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "time": "2026-11-12T02:37:29.200757+00:00"}
```

## 8. Keep the evidence and clean up

Your local observations are in .lab/events.jsonl, including the original Lambda log messages. Inspect and keep them before stopping the environment. Cleanup deletes this session’s emulated resources; it keeps the local evidence files.


```bash
python lab.py cleanup
tail -n 5 .lab/events.jsonl
```


- Find cleanup_completed. The saved resource state is removed; .lab/events.jsonl remains.
- Native Linux: stop terminal A with Ctrl+C. Docker: before exiting, copy .lab out from a host terminal using docker cp sqs-lambda-practice:/opt/lab/.lab ./practice-logs. Then exit the container shell.
- If the emulator was restarted mid-lab, its in-memory resources are gone. Run python lab.py reset, then prepare to start over. Logs are retained, so use timestamps to separate attempts.

What evidence would you use to explain this incident to someone else?

Keep the original message ID, the three failure log entries, the diagnostic DLQ read, the applied fix, the redrive task, and the final success. That tells a more useful story than a screenshot of an empty queue.

Do not publish the raw emulator startup log without reviewing it: it can contain generated local credentials. The events file does not include those credentials.

## Explain the lifecycle from your own logs

You should be able to distinguish a delivery attempt, an application failure, a diagnostic receive, and a successful recovery. If any check failed, use inspect and the saved logs before starting over.

## References

- [AWS Emulator · requirements and installation](https://docs.aws.amazon.com/emulator/latest/userguide/setting-up.html)
- [AWS Emulator · native Linux setup](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-linux.html)
- [Lambda · configuring SQS event sources](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html)
- [Lambda · handling errors for SQS](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)
- [SQS · dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [SQS · redrive and message identity](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html)
