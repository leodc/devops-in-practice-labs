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
        self.secrets = client("secretsmanager")
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

    def read_version(self, **selector):
        response = self.secrets.get_secret_value(SecretId=self.state["secret"], **selector)
        # Only validation results and version metadata enter the log, never SecretString.
        try:
            value = json.loads(response["SecretString"])
            valid = (isinstance(value, dict) and value.get("schema") == 1
                     and isinstance(value.get("api_key"), str) and bool(value["api_key"]))
        except (ValueError, KeyError):
            valid = False
        return {"version_id": response["VersionId"],
                "stages": response.get("VersionStages", []), "valid": valid}

    def prepare(self):
        require(not self.state, "A session already exists. Inspect it or run cleanup first.")
        name = "practice-secret-" + uuid4().hex[:10]
        self.state = {"emulator": self.fingerprint, "phase": "preparing", "secret": name}
        self.save()
        emit("environment", endpoint=ENDPOINT, boto3=boto3.__version__,
             emulator=subprocess.check_output(["aws-emulator", "--version"], text=True).strip(),
             lab_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        result = self.secrets.create_secret(Name=name,
            SecretString=json.dumps({"schema": 1, "api_key": "local-example-not-a-real-key"}))
        self.state["good_version"] = result["VersionId"]
        (ROOT / "recovery.json").write_text('{"version_id": "choose-after-diagnosis"}\n')
        self.set_phase("prepared")
        emit("consumer_read", **self.read_version(), result="ACCEPTED")

    def inspect(self):
        require(self.state, "Run prepare first.")
        versions = self.secrets.list_secret_version_ids(SecretId=self.state["secret"], IncludeDeprecated=True)["Versions"]
        emit("versions", phase=self.state["phase"], secret=self.state["secret"],
             versions=[{"version_id": v["VersionId"], "stages": v["VersionStages"]} for v in versions])
        emit("current_version", **self.read_version())

    def publish_bad(self):
        self.phase("prepared")
        result = self.secrets.put_secret_value(SecretId=self.state["secret"],
            SecretString=json.dumps({"schema": 2, "token": "local-example-not-a-real-token"}))
        self.state["bad_version"] = result["VersionId"]
        self.save()
        current = self.read_version()
        require(current["version_id"] == result["VersionId"] and not current["valid"],
                "The new version did not become current or was not rejected by the consumer.")
        emit("consumer_read", **current, result="REJECTED", reason="consumer_requires_schema_1_and_api_key")
        self.set_phase("broken")

    def diagnose(self):
        self.phase("broken", "diagnosed")
        versions = self.secrets.list_secret_version_ids(SecretId=self.state["secret"], IncludeDeprecated=True)["Versions"]
        for version in versions:
            emit("version_checked", **self.read_version(VersionId=version["VersionId"]))
        require(self.read_version(VersionId=self.state["good_version"])["valid"], "The original version is not valid.")
        require(not self.read_version()["valid"], "The current version no longer reproduces the failure.")
        emit("diagnosis", reason="AWSCURRENT_points_to_incompatible_schema",
             recovery_file="recovery.json", current_version=self.state["bad_version"])
        self.set_phase("diagnosed")

    def repair(self):
        self.phase("diagnosed")
        selected = json.loads((ROOT / "recovery.json").read_text()).get("version_id")
        require(selected == self.state["good_version"], "Set recovery.json version_id to the valid version from diagnose.")
        require(self.read_version(VersionId=selected)["valid"], "The selected version fails consumer validation.")
        current = self.read_version()
        require(current["version_id"] == self.state["bad_version"], "AWSCURRENT changed. Inspect before moving its label.")
        self.secrets.update_secret_version_stage(SecretId=self.state["secret"], VersionStage="AWSCURRENT",
            MoveToVersionId=selected, RemoveFromVersionId=current["version_id"])
        self.set_phase("repaired")
        emit("label_moved", label="AWSCURRENT", from_version=current["version_id"], to_version=selected)

    def verify(self):
        self.phase("repaired", "verified")
        current = wait_for("valid current version", self.read_version,
                           lambda r: r["valid"] and r["version_id"] == self.state["good_version"])
        previous = self.read_version(VersionStage="AWSPREVIOUS")
        require(previous["version_id"] == self.state["bad_version"], "AWSPREVIOUS did not move to the rejected version.")
        self.set_phase("verified")
        emit("verification", result="PASS", current=current, previous=previous,
             consumer="fresh_read_without_version_selector")

    def cleanup(self):
        require(self.state, "No saved lab session to clean up.")
        try:
            self.secrets.delete_secret(SecretId=self.state["secret"], ForceDeleteWithoutRecovery=True)
        except ClientError as error:
            if error.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        def gone():
            try:
                self.secrets.describe_secret(SecretId=self.state["secret"])
                return False
            except ClientError as error:
                if error.response["Error"]["Code"] == "ResourceNotFoundException":
                    return True
                raise
        wait_for("secret deleted", gone, bool)
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
    parser.add_argument("stage", choices=["prepare", "inspect", "publish-bad", "diagnose", "repair", "verify", "cleanup", "reset"])
    args = parser.parse_args()
    try:
        if args.stage == "reset":
            reset()
        else:
            getattr(Lab(), args.stage.replace("-", "_"))()
    except Exception as error:
        # Do not log arbitrary SDK error text: secret payloads must never enter traces.
        emit("error", error_type=type(error).__name__,
             message=str(error) if isinstance(error, (RuntimeError, TimeoutError)) else "Stage failed; inspect the helper and saved state.")
        sys.exit(1)
