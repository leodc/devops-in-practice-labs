"""A staged local experiment. Never connects to an AWS account."""

import argparse
import configparser
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".lab"
STATE = WORK / "state.json"
ENDPOINT = "https://127.0.0.1:19397"
EMULATOR = Path.home() / ".aws/emulator/19397"


def emit(event, **fields):
    row = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    line = json.dumps(row, sort_keys=True)
    print(line, flush=True)
    WORK.mkdir(exist_ok=True)
    with (WORK / "events.jsonl").open("a") as file:
        file.write(line + "\n")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def wait_for(label, read, accept, seconds=90):
    deadline = time.monotonic() + seconds
    value = None
    while time.monotonic() < deadline:
        value = read()
        if accept(value):
            return value
        time.sleep(0.5)
    raise TimeoutError(f"{label}: not ready after {seconds}s. Read .lab/events.jsonl; last response: {value}")


class Lab:
    def __init__(self):
        credential_file = EMULATOR / "emulator_credentials"
        require(credential_file.is_file(), "Start the emulator on port 19397 in another terminal first.")
        self.fingerprint = hashlib.sha256(credential_file.read_bytes()).hexdigest()
        # Replace the SDK environment before constructing clients: no host profiles or credentials.
        for key in list(os.environ):
            if key.startswith("AWS_"):
                del os.environ[key]
        os.environ.update({
            "AWS_CONFIG_FILE": str(EMULATOR / "config"),
            "AWS_SHARED_CREDENTIALS_FILE": str(credential_file),
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_CA_BUNDLE": str(EMULATOR / "ca.pem"),
        })
        credentials = configparser.ConfigParser()
        credentials.read(credential_file)
        local = credentials["default"]
        session = boto3.Session(
            aws_access_key_id=local["aws_access_key_id"],
            aws_secret_access_key=local["aws_secret_access_key"],
            region_name="us-east-1",
        )
        config = Config(connect_timeout=3, read_timeout=10,
                        retries={"total_max_attempts": 1}, inject_host_prefix=False)
        def client(name):
            return session.client(name, endpoint_url=ENDPOINT,
                                  verify=str(EMULATOR / "ca.pem"), config=config)
        require(client("sts").get_caller_identity()["Account"] == "000000000000",
                "The endpoint did not identify the emulator account.")
        self.sqs = client("sqs")
        self.state = json.loads(STATE.read_text()) if STATE.exists() else {}
        require(not self.state or self.state["emulator"] == self.fingerprint,
                "The emulator was restarted. Its old resources are gone. Run: python lab.py reset")

    def save(self):
        WORK.mkdir(exist_ok=True)
        temporary = STATE.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n")
        temporary.chmod(0o600)
        temporary.replace(STATE)

    def phase(self, *allowed):
        require(self.state.get("phase") in allowed,
                f"Expected stage {allowed}; current: {self.state.get('phase', 'not prepared')}. Read .lab/events.jsonl.")

    def set_phase(self, phase):
        self.state["phase"] = phase
        self.save()
        emit("stage_completed", stage=phase)

    def prepare(self):
        require(not self.state, "A session exists. Run cleanup before starting again.")
        self.state = {"emulator": self.fingerprint, "phase": "preparing", "receives": 0}
        self.save()
        emit("environment", endpoint=ENDPOINT, boto3=boto3.__version__,
             emulator=subprocess.check_output(["aws-emulator", "--version"], text=True).strip(),
             source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                            for name in ("lab.py", "Dockerfile", "requirements.txt", "validate.sh")})
        self.state["queue"] = self.sqs.create_queue(QueueName="practice-returns-" + uuid4().hex[:10],
            Attributes={"VisibilityTimeout": "3"})["QueueUrl"]
        self.save()
        response = self.sqs.send_message(QueueUrl=self.state["queue"], MessageBody="hello-again")
        self.state["message_id"] = response["MessageId"]
        self.set_phase("prepared")
        emit("sent", message_id=response["MessageId"], body="hello-again", visibility_seconds=3)

    def next_message(self, visibility):
        response = wait_for("message available", lambda: self.sqs.receive_message(
            QueueUrl=self.state["queue"], MaxNumberOfMessages=1, WaitTimeSeconds=1,
            VisibilityTimeout=visibility, MessageSystemAttributeNames=["ApproximateReceiveCount"]),
            lambda r: bool(r.get("Messages")), seconds=15)
        message = response["Messages"][0]
        require(message["MessageId"] == self.state["message_id"] and message["Body"] == "hello-again",
                "The received message does not match the one sent by this lab.")
        return message

    def receive(self):
        self.phase("prepared", "received")
        message = self.next_message(3)
        count = int(message["Attributes"]["ApproximateReceiveCount"])
        require(count > self.state["receives"], "Receive count did not increase.")
        self.state["receives"] = count
        self.set_phase("received")
        emit("received_without_delete", message_id=message["MessageId"], body=message["Body"],
             receive_count=count, visibility_seconds=3)

    def ack(self):
        self.phase("received")
        require(self.state["receives"] >= 2, "Run receive again to observe redelivery before deleting.")
        # The learner may pause for any length of time. Receive again so deletion uses a fresh handle.
        message = self.next_message(30)
        emit("received_for_delete", message_id=message["MessageId"],
             receive_count=int(message["Attributes"]["ApproximateReceiveCount"]))
        self.sqs.delete_message(QueueUrl=self.state["queue"], ReceiptHandle=message["ReceiptHandle"])
        self.set_phase("deleted")
        emit("deleted", message_id=message["MessageId"])

    def counts(self):
        response = self.sqs.get_queue_attributes(QueueUrl=self.state["queue"], AttributeNames=[
            "ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible", "ApproximateNumberOfMessagesDelayed"])
        return {key: int(value) for key, value in response["Attributes"].items()}

    def verify(self):
        self.phase("deleted", "verified")
        counts = wait_for("queue empty", self.counts, lambda r: sum(r.values()) == 0, seconds=15)
        messages = self.sqs.receive_message(QueueUrl=self.state["queue"], WaitTimeSeconds=1).get("Messages", [])
        require(not messages, "A message was received after deletion. Inspect the trace.")
        self.set_phase("verified")
        emit("verification", result="PASS", messages_returned=0, counts=counts)

    def cleanup(self):
        require(self.state, "No saved session to clean up.")
        if self.state.get("queue"):
            try:
                self.sqs.delete_queue(QueueUrl=self.state["queue"])
            except ClientError as error:
                if error.response["Error"]["Code"] not in ("AWS.SimpleQueueService.NonExistentQueue", "QueueDoesNotExist"):
                    raise
        STATE.unlink()
        emit("cleanup_completed", logs=".lab/events.jsonl")

def reset():
    require(STATE.exists(), "No saved session to reset.")
    state = json.loads(STATE.read_text())
    credentials = EMULATOR / "emulator_credentials"
    require(not credentials.exists() or hashlib.sha256(credentials.read_bytes()).hexdigest() != state["emulator"],
            "This session's emulator is still running. Use cleanup, not reset.")
    STATE.unlink()
    emit("stale_session_reset", note="No resources changed. Logs retained.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "receive", "ack", "verify", "cleanup", "reset"])
    args = parser.parse_args()
    try:
        if args.stage == "reset":
            reset()
        else:
            getattr(Lab(), args.stage)()
    except Exception as error:
        emit("error", error_type=type(error).__name__, message=str(error))
        sys.exit(1)
