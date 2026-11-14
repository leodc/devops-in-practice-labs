# SQS: why did the message come back?

Receive the same message twice and see what changes when you delete it.

Reading an SQS message does not delete it. See it happen with one queue, one message, and four steps.

Allow about five minutes for the exercise once the environment is ready.

## Set up your environment

### 1. Clone the repository

If you already have the repository, run git pull from its root and enter this lab directory.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-message-returns
```

### Linux

#### 2. Start the emulator

Install AWS Emulator 1.0.322 and Python with pip and venv. Then prepare the environment and start the emulator.

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
cd devops-in-practice-labs/sqs-message-returns
source .venv/bin/activate
```

Continue in terminal B when the emulator is ready.

### Docker

#### 2. Enter the lab environment

The container includes AWS Emulator 1.0.322 and Python. Logs stay in .lab on your computer.

**Your terminal → container shell**

```bash
bash docker-lab.sh
```

- Use Bash and Docker with Linux containers; on Windows, run these commands in WSL.

Continue in the shell that opens.

## 1. Receive a message without deleting it

Create the queue, send hello-again, and receive it once.

```bash
python lab.py prepare
python lab.py receive
```

- Find received_without_delete with receive_count 1 and save its message_id.

Has the message left the queue?

ReceiveMessage hides it temporarily. The helper does not call DeleteMessage; in this exercise, the message becomes visible again after three seconds.

## 2. Receive the same message again

Run receive again. The command waits if the message is still hidden.

```bash
python lab.py receive
```

- Compare message_id: it is unchanged. receive_count is now 2.

Did anyone have to send another message?

No. The original message became available again because it was not deleted. That lets unfinished work be attempted again. Repeating this command increases the count further.

### Reference trace

```text
{"body": "hello-again", "event": "received_without_delete", "message_id": "63b1c706-8395-4a85-aad5-fd0f644083c5", "receive_count": 1, "time": "2026-11-14T10:00:38.879509+00:00", "visibility_seconds": 3}
{"body": "hello-again", "event": "received_without_delete", "message_id": "63b1c706-8395-4a85-aad5-fd0f644083c5", "receive_count": 2, "time": "2026-11-14T10:00:42.174903+00:00", "visibility_seconds": 3}
```

## 3. Delete it and check the result

Run ack to receive it with a fresh receipt handle and delete it immediately. Then check the queue.

```bash
python lab.py ack
python lab.py verify
```

- Find received_for_delete for another receive, followed by deleted.
- Find verification with PASS, zero messages, and none in flight.

Why does ack receive it again before deleting?

You may have paused between steps. A fresh receive gets a current receipt handle for DeleteMessage. Open ack in lab.py to see both API calls.

### Reference trace

```text
{"counts": {"ApproximateNumberOfMessages": 0, "ApproximateNumberOfMessagesDelayed": 0, "ApproximateNumberOfMessagesNotVisible": 0}, "event": "verification", "messages_returned": 0, "result": "PASS", "time": "2026-11-14T10:00:46.541568+00:00"}
```

## 4. Keep the sequence and finish

Delete the queue and read the full trace.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Follow the same message_id from sent through deleted.
- Linux: stop terminal A with Ctrl+C. Docker: exit the shell. .lab/events.jsonl stays on your computer.

What was missing after receiving the message?

Deleting it after completing the work. Receiving a message and acknowledging completion are separate operations. If you restarted the emulator before finishing, run python lab.py reset before prepare.

## Receiving is not deleting

You observed the same message being delivered again and checked its deletion. That distinction also matters when a function processes messages for you.

## References

- [SQS · Visibility timeout](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)
- [SQS · DeleteMessage](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_DeleteMessage.html)
- [Code and reference traces](https://github.com/leodc/devops-in-practice-labs/tree/main/sqs-message-returns)
