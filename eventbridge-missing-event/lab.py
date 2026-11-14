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
    raise TimeoutError(f"{label}: not ready after {seconds}s. Run inspect; last response: {value}")


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
        self.sqs, self.events = [client(name) for name in ("sqs", "events")]
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
                f"Expected stage {allowed}; current: {self.state.get('phase', 'not prepared')}. Run inspect.")

    def set_phase(self, phase):
        self.state["phase"] = phase
        self.save()
        emit("stage_completed", stage=phase)

    def prepare(self):
        require(not self.state, "A session exists. Run inspect or cleanup first.")
        initial = (ROOT / "pattern.json").read_text()
        require(not self.matches(initial, self.event("starting-pattern-check")),
                "Restore pattern.json detail-type to order.created before preparing a new run.")
        name = "practice-events-" + uuid4().hex[:10]
        self.state = {"name": name, "bus": name, "rule": "orders", "phase": "preparing", "emulator": self.fingerprint}
        self.save()
        emit("environment", endpoint=ENDPOINT, boto3=boto3.__version__,
             emulator_version=subprocess.check_output(["aws-emulator", "--version"], text=True).strip(),
             source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / "lab.py", ROOT / "pattern.json", ROOT / "Dockerfile", ROOT / "requirements.txt"]})
        self.events.create_event_bus(Name=name)
        url = self.sqs.create_queue(QueueName=name)["QueueUrl"]
        self.state["queue"] = url
        self.save()
        arn = self.sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        rule = self.events.put_rule(Name="orders", EventBusName=name, EventPattern=(ROOT / "pattern.json").read_text())["RuleArn"]
        policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "events.amazonaws.com"}, "Action": "sqs:SendMessage", "Resource": arn, "Condition": {"ArnEquals": {"aws:SourceArn": rule}}}]}
        self.sqs.set_queue_attributes(QueueUrl=url, Attributes={"Policy": json.dumps(policy)})
        result = self.events.put_targets(Rule="orders", EventBusName=name, Targets=[{"Id": "queue", "Arn": arn}])
        require(result["FailedEntryCount"] == 0, f"Target creation failed: {result}")
        self.set_phase("prepared")

    def pattern(self):
        return self.events.describe_rule(Name=self.state["rule"], EventBusName=self.state["bus"])["EventPattern"]

    def event(self, correlation, detail_type="OrderCreated"):
        return {"version": "0", "id": correlation, "account": "000000000000", "source": "practice.orders", "detail-type": detail_type,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "region": "us-east-1", "resources": [], "detail": {"correlation_id": correlation, "order_id": "order-42"}}

    def matches(self, pattern, event):
        return self.events.test_event_pattern(EventPattern=pattern, Event=json.dumps(event))["Result"]

    def publish(self, event):
        result = self.events.put_events(Entries=[{"Source": event["source"], "DetailType": event["detail-type"], "Detail": json.dumps(event["detail"]), "EventBusName": self.state["bus"]}])
        emit("published", correlation_id=event["detail"]["correlation_id"], detail_type=event["detail-type"], failed_entry_count=result["FailedEntryCount"], entries=result["Entries"])
        require(result["FailedEntryCount"] == 0 and result["Entries"][0].get("EventId"), "PutEvents failed. Inspect the recorded response.")

    def inspect(self):
        require(self.state, "Run prepare first.")
        emit("inspection", phase=self.state["phase"], pattern=json.loads(self.pattern()),
             queue=self.sqs.get_queue_attributes(QueueUrl=self.state["queue"], AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"])["Attributes"])

    def send(self):
        self.phase("prepared")
        event = self.event(uuid4().hex)
        require(not self.matches(self.pattern(), event), "The starting pattern already matches. Restore pattern.json before preparing a fresh session.")
        self.state["original"] = event
        self.save()
        self.publish(event)
        self.set_phase("sent")

    def diagnose(self):
        self.phase("sent", "diagnosed")
        event = self.state["original"]
        pattern = self.pattern()
        matched = self.matches(pattern, event)
        emit("pattern_diagnosis", correlation_id=event["detail"]["correlation_id"], event_detail_type=event["detail-type"], pattern=json.loads(pattern), matched=matched)
        require(not matched, "The rule now matches. Inspect the current configuration.")
        self.set_phase("diagnosed")

    def repair(self):
        self.phase("diagnosed")
        pattern = (ROOT / "pattern.json").read_text()
        json.loads(pattern)
        positive = self.matches(pattern, self.state["original"])
        negative = self.matches(pattern, self.event("negative-check", "OrderCancelled"))
        emit("candidate_pattern", positive_matches=positive, negative_matches=negative, pattern=json.loads(pattern))
        require(positive and not negative, "The pattern must match OrderCreated and reject OrderCancelled. Edit pattern.json.")
        self.events.put_rule(Name=self.state["rule"], EventBusName=self.state["bus"], EventPattern=pattern)
        wait_for("rule update", self.pattern, lambda current: self.matches(current, self.state["original"]) and not self.matches(current, self.event("negative-check", "OrderCancelled")))
        emit("rule_updated", pattern=json.loads(self.pattern()), pattern_sha256=hashlib.sha256((ROOT / "pattern.json").read_bytes()).hexdigest())
        self.set_phase("repaired")

    def resend(self):
        self.phase("repaired")
        positive = self.event(uuid4().hex)
        negative = self.event(uuid4().hex, "OrderCancelled")
        self.state.update(positive=positive, negative=negative)
        self.save()
        self.publish(positive)
        self.publish(negative)
        self.set_phase("resent")

    def verify(self):
        self.phase("resent", "verified")
        pattern = self.pattern()
        positive_matches = self.matches(pattern, self.state["positive"])
        negative_matches = self.matches(pattern, self.state["negative"])
        require(positive_matches and not negative_matches, "The deployed pattern does not select the intended event.")
        wanted = self.state["positive"]["detail"]["correlation_id"]
        rejected = self.state["negative"]["detail"]["correlation_id"]
        received = set(self.state.get("received", []))
        deadline = time.monotonic() + 30
        # Continue a short observation window after success; emptiness is not proof of filtering.
        observation_until = time.monotonic() + 3 if wanted in received else deadline
        while time.monotonic() < min(deadline, observation_until):
            result = self.sqs.receive_message(QueueUrl=self.state["queue"], MaxNumberOfMessages=10, WaitTimeSeconds=1)
            for message in result.get("Messages", []):
                body = json.loads(message["Body"])
                correlation = body.get("detail", {}).get("correlation_id")
                emit("queue_delivery", correlation_id=correlation, detail_type=body.get("detail-type"), event_id=body.get("id"))
                require(correlation != rejected, "The negative control was delivered unexpectedly.")
                require(correlation == wanted, "An unexpected event was delivered. Inspect its correlation ID.")
                received.add(correlation)
                self.state["received"] = sorted(received)
                self.save()
                self.sqs.delete_message(QueueUrl=self.state["queue"], ReceiptHandle=message["ReceiptHandle"])
                observation_until = min(observation_until, time.monotonic() + 3)
        require(wanted in received, "The matching event was not observed within 30 seconds. Run verify again.")
        emit("verification", positive_delivered=True, positive_pattern_match=positive_matches, negative_pattern_match=negative_matches,
             correlation_id=wanted, negative_delivery_observed=False, observation="bounded; negative filtering established by TestEventPattern")
        self.set_phase("verified")

    def cleanup(self):
        require(self.state, "No local session exists.")
        # Delete only the unique resources recorded for this session.
        def remove(call, **kwargs):
            try:
                return call(**kwargs)
            except ClientError as error:
                if error.response["Error"]["Code"] not in ("ResourceNotFoundException", "AWS.SimpleQueueService.NonExistentQueue", "QueueDoesNotExist"):
                    raise
        result = remove(self.events.remove_targets, Rule=self.state["rule"], EventBusName=self.state["bus"], Ids=["queue"])
        require(not result or result.get("FailedEntryCount", 0) == 0, f"Target removal failed: {result}")
        remove(self.events.delete_rule, Name=self.state["rule"], EventBusName=self.state["bus"])
        remove(self.events.delete_event_bus, Name=self.state["bus"])
        if self.state.get("queue"):
            remove(self.sqs.delete_queue, QueueUrl=self.state["queue"])
        emit("cleanup", name=self.state["name"], logs=".lab/events.jsonl")
        STATE.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "inspect", "send", "diagnose", "repair", "resend", "verify", "cleanup", "reset"])
    args = parser.parse_args()
    if args.stage == "reset":
        # Keep evidence from the previous session; only forget stale resource identifiers.
        require(STATE.exists(), "No state to reset.")
        old = json.loads(STATE.read_text())
        credential = EMULATOR / "emulator_credentials"
        require(credential.exists() and old["emulator"] != hashlib.sha256(credential.read_bytes()).hexdigest(), "Reset is only for a restarted emulator. Use cleanup for a live session.")
        STATE.unlink()
        emit("state_reset")
        return
    getattr(Lab(), args.stage)()


if __name__ == "__main__":
    try:
        main()
    except (ClientError, RuntimeError, TimeoutError, ValueError, OSError) as error:
        emit("error", error_type=type(error).__name__, message=str(error))
        sys.exit(1)
