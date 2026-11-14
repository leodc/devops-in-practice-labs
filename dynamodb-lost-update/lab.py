"""Observe a lost update, then protect a DynamoDB write with a version condition."""

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
        self.ddb = client("dynamodb")
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

    def config(self):
        value = json.loads((ROOT / "writer.json").read_text())
        require(set(value) == {"check_version"} and type(value["check_version"]) is bool,
                'writer.json must contain only "check_version": true or false.')
        return value

    def item(self):
        result = self.ddb.get_item(TableName=self.state["table"],
            Key={"id": {"S": "counter"}}, ConsistentRead=True)["Item"]
        return {key: int(result[key]["N"]) for key in ("value", "version")}

    def seed(self):
        self.ddb.put_item(TableName=self.state["table"], Item={
            "id": {"S": "counter"}, "value": {"N": "0"}, "version": {"N": "0"}})
        emit("counter_reset", item=self.item())

    def write(self, writer, snapshot):
        conditional = self.state["applied_writer"]["check_version"]
        names = {"#value": "value", "#version": "version"}
        values = {":next": {"N": str(snapshot["value"] + 1)},
                  ":version": {"N": str(snapshot["version"] + 1)}}
        extra = {}
        if conditional:
            extra["ConditionExpression"] = "#version = :expected"
            values[":expected"] = {"N": str(snapshot["version"])}
        try:
            response = self.ddb.update_item(TableName=self.state["table"],
                Key={"id": {"S": "counter"}},
                UpdateExpression="SET #value = :next, #version = :version",
                ExpressionAttributeNames=names, ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW", **extra)
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            emit("write_rejected", writer=writer, snapshot=snapshot,
                 code=error.response["Error"]["Code"], check_version=conditional,
                 observed=self.item())
            return False
        observed = {key: int(response["Attributes"][key]["N"]) for key in ("value", "version")}
        emit("write_accepted", writer=writer, snapshot=snapshot,
             check_version=conditional, observed=observed)
        return True

    def prepare(self):
        require(not self.state, "A session exists. Use inspect or cleanup first.")
        require(self.config()["check_version"] is False,
                "Start with check_version false in writer.json.")
        self.state = {"table": "practice-ddb-" + uuid4().hex[:10],
                      "emulator": self.fingerprint, "phase": "preparing",
                      "applied_writer": self.config()}
        self.save()
        emit("environment", endpoint=ENDPOINT, boto3=boto3.__version__,
             emulator=subprocess.check_output(["aws-emulator", "--version"], text=True).strip(),
             source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                            for name in ("lab.py", "writer.json", "requirements.txt", "Dockerfile", "validate.py")})
        self.ddb.create_table(TableName=self.state["table"],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}], BillingMode="PAY_PER_REQUEST")
        self.ddb.get_waiter("table_exists").wait(TableName=self.state["table"],
            WaiterConfig={"Delay": 1, "MaxAttempts": 30})
        self.seed()
        self.set_phase("prepared")
        self.inspect()

    def inspect(self):
        require(self.state, "Run prepare first.")
        table = self.ddb.describe_table(TableName=self.state["table"])["Table"]
        emit("inspection", stage=self.state["phase"], table=table["TableName"],
             status=table["TableStatus"], item=self.item(),
             applied_writer=self.state["applied_writer"], file_writer=self.config())

    def pair(self):
        snapshots = {writer: self.item() for writer in ("A", "B")}
        require(snapshots == {"A": {"value": 0, "version": 0}, "B": {"value": 0, "version": 0}},
                "The comparison requires two snapshots of the initial counter.")
        self.state["snapshots"] = snapshots
        self.save()
        emit("snapshots_read", snapshots=snapshots, consistent_read=True)
        require(self.write("A", snapshots["A"]), "Writer A was unexpectedly rejected.")
        return self.write("B", snapshots["B"])

    def collide(self):
        self.phase("prepared")
        self.set_phase("collision_started")
        require(self.pair(), "The unprotected writer was unexpectedly rejected.")
        self.set_phase("collided")
        self.inspect()

    def diagnose(self):
        self.phase("collided", "diagnosed")
        observed = self.item()
        require(observed == {"value": 1, "version": 1}, "Expected one lost increment.")
        emit("lost_update", accepted_writes=2, expected_value=2, observed=observed,
             cause="Both writers calculated 0 + 1 before either write.")
        self.set_phase("diagnosed")

    def repair(self):
        self.phase("diagnosed")
        configuration = self.config()
        require(configuration["check_version"] is True, "Set check_version to true in writer.json first.")
        self.state["applied_writer"] = configuration
        self.set_phase("repaired")
        emit("writer_applied", configuration=configuration,
             writer_sha256=hashlib.sha256((ROOT / "writer.json").read_bytes()).hexdigest())

    def replay(self):
        self.phase("repaired")
        self.set_phase("replay_started")
        # Reset the fixture to compare the same two writes, not to recover the lost update.
        self.seed()
        require(not self.pair(), "The stale writer succeeded despite the version condition.")
        self.state["rejected_snapshot"] = self.state["snapshots"]["B"]
        self.set_phase("conflict")
        self.inspect()

    def retry(self):
        self.phase("conflict")
        self.set_phase("retry_started")
        fresh = self.item()
        require(fresh == {"value": 1, "version": 1}, "Unexpected counter before retry.")
        emit("snapshot_refreshed", writer="B", before=self.state["rejected_snapshot"], after=fresh)
        require(self.write("B", fresh), "Retry was unexpectedly rejected.")
        self.set_phase("retried")

    def verify(self):
        self.phase("retried", "verified")
        observed = self.item()
        require(observed == {"value": 2, "version": 2}, "Both increments must survive.")
        require(self.state["applied_writer"]["check_version"] is True, "Version protection is disabled.")
        emit("verification", result="PASS", observed=observed, increments=2)
        self.set_phase("verified")

    def cleanup(self):
        require(self.state, "No saved session to clean up.")
        try:
            self.ddb.delete_table(TableName=self.state["table"])
            self.ddb.get_waiter("table_not_exists").wait(TableName=self.state["table"],
                WaiterConfig={"Delay": 1, "MaxAttempts": 30})
        except ClientError as error:
            if error.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        STATE.unlink()
        emit("cleanup_completed", table=self.state["table"])


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
    parser.add_argument("stage", choices=["prepare", "inspect", "collide", "diagnose", "repair", "replay",
                                         "retry", "verify", "cleanup", "reset"])
    args = parser.parse_args()
    try:
        if args.stage == "reset":
            reset()
        else:
            getattr(Lab(), args.stage)()
    except Exception as error:
        emit("error", error_type=type(error).__name__, message=str(error))
        sys.exit(1)
