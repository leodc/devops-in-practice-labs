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
                        retries={"total_max_attempts": 1}, inject_host_prefix=False,
                        s3={"addressing_style": "path"})
        def client(name):
            return session.client(name, endpoint_url=ENDPOINT,
                                  verify=str(EMULATOR / "ca.pem"), config=config)
        require(client("sts").get_caller_identity()["Account"] == "000000000000",
                "The endpoint did not identify the emulator account.")
        self.s3 = client("s3")
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

    def versions(self):
        rows = []
        for page in self.s3.get_paginator("list_object_versions").paginate(Bucket=self.state["bucket"]):
            for kind in ("Versions", "DeleteMarkers"):
                for version in page.get(kind, []):
                    rows.append({"version_id": version["VersionId"], "key": version["Key"],
                                 "latest": version["IsLatest"], "delete_marker": kind == "DeleteMarkers"})
        return rows

    def read(self, version=None):
        response = self.s3.get_object(Bucket=self.state["bucket"], Key="config.json",
                                      **({"VersionId": version} if version else {}))
        return response["Body"].read(), response["VersionId"]

    def prepare(self):
        require(not self.state, "A session already exists. Run inspect or cleanup first.")
        self.state = {"bucket": "practice-s3-" + uuid4().hex[:10],
                      "emulator": self.fingerprint, "phase": "preparing"}
        self.save()
        hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                  for name in ("lab.py", "Dockerfile", "requirements.txt", "docker-shell.sh",
                               "docker-lab.sh", "start-emulator.sh", "validate.sh")}
        emit("environment", endpoint=ENDPOINT, boto3=boto3.__version__,
             emulator=subprocess.check_output(["aws-emulator", "--version"], text=True).strip(),
             source_sha256=hashes)
        self.s3.create_bucket(Bucket=self.state["bucket"])
        self.s3.put_bucket_versioning(Bucket=self.state["bucket"],
                                      VersioningConfiguration={"Status": "Enabled"})
        good = b'{"service":"checkout","timeout_seconds":30}\n'
        self.state["original_sha256"] = hashlib.sha256(good).hexdigest()
        self.state["original_version"] = self.s3.put_object(Bucket=self.state["bucket"],
            Key="config.json", Body=good, ContentType="application/json")["VersionId"]
        self.save()
        (ROOT / "recovery.json").write_text('{\n  "version_id": "choose-a-version-from-diagnose"\n}\n')
        emit("original_uploaded", version_id=self.state["original_version"],
             sha256=self.state["original_sha256"], content=good.decode().strip())
        self.set_phase("prepared")

    def inspect(self):
        require(self.state, "Run prepare first.")
        emit("session", stage=self.state["phase"], bucket=self.state["bucket"],
             versioning=self.s3.get_bucket_versioning(Bucket=self.state["bucket"]).get("Status"))
        try:
            content, version = self.read()
            emit("current_object", version_id=version, content=content.decode().strip(),
                 sha256=hashlib.sha256(content).hexdigest())
        except ClientError as error:
            if error.response["Error"]["Code"] != "NoSuchKey":
                raise
            emit("current_object_missing", error_code=error.response["Error"]["Code"],
                 http_status=error.response["ResponseMetadata"]["HTTPStatusCode"])
        for row in self.versions():
            emit("version", **row)

    def break_object(self):
        self.phase("prepared")
        bad = b'{"service":"checkout","timeout_seconds":0}\n'
        version = self.s3.put_object(Bucket=self.state["bucket"], Key="config.json",
                                     Body=bad, ContentType="application/json")["VersionId"]
        emit("bad_configuration_uploaded", version_id=version, content=bad.decode().strip())
        self.state["bad_version"] = version
        self.save()
        response = self.s3.delete_object(Bucket=self.state["bucket"], Key="config.json")
        require(response.get("DeleteMarker") is True, "Expected a versioned delete marker.")
        self.state["delete_marker"] = response["VersionId"]
        self.save()
        emit("object_deleted", delete_marker=response["DeleteMarker"], version_id=response["VersionId"])
        self.set_phase("broken")

    def diagnose(self):
        self.phase("broken", "diagnosed")
        self.inspect()
        for row in self.versions():
            if not row["delete_marker"]:
                content, version = self.read(row["version_id"])
                emit("version_content", version_id=version, content=content.decode().strip(),
                     sha256=hashlib.sha256(content).hexdigest())
        self.set_phase("diagnosed")

    def repair(self):
        self.phase("diagnosed")
        chosen = json.loads((ROOT / "recovery.json").read_text())["version_id"]
        require(any(row["version_id"] == chosen and not row["delete_marker"] for row in self.versions()),
                "Set version_id in recovery.json to an object version from diagnose.")
        content, _ = self.read(chosen)
        config = json.loads(content)
        require(config.get("timeout_seconds", 0) > 0, "That configuration has an invalid timeout. Choose another version.")
        response = self.s3.copy_object(Bucket=self.state["bucket"], Key="config.json",
            CopySource={"Bucket": self.state["bucket"], "Key": "config.json", "VersionId": chosen})
        require(response["VersionId"] != chosen, "CopyObject should create a new version.")
        self.state["recovered_version"] = response["VersionId"]
        self.save()
        emit("version_restored", source_version=chosen, new_version=response["VersionId"])
        self.set_phase("repaired")

    def verify(self):
        self.phase("repaired", "verified")
        content, version = self.read()
        digest = hashlib.sha256(content).hexdigest()
        require(digest == self.state["original_sha256"], "Current content differs from the original configuration.")
        require(version == self.state["recovered_version"], "The restored version is not current.")
        versions = self.versions()
        require(any(row["version_id"] == self.state["delete_marker"] and row["delete_marker"] for row in versions),
                "The original delete marker should remain in the history.")
        (WORK / "recovered-config.json").write_bytes(content)
        emit("recovery_verified", version_id=version, sha256=digest, matches_original=True,
             history_entries=len(versions), file=".lab/recovered-config.json")
        self.set_phase("verified")

    def cleanup(self):
        require(self.state, "No session to clean up.")
        for row in self.versions():
            self.s3.delete_object(Bucket=self.state["bucket"], Key=row["key"], VersionId=row["version_id"])
        self.s3.delete_bucket(Bucket=self.state["bucket"])
        STATE.unlink()
        emit("cleanup_completed", bucket=self.state["bucket"], logs=".lab/events.jsonl")


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
    parser.add_argument("stage", choices=["prepare", "inspect", "break", "diagnose", "repair", "verify", "cleanup", "reset"])
    args = parser.parse_args()
    try:
        if args.stage == "reset":
            reset()
        else:
            getattr(Lab(), "break_object" if args.stage == "break" else args.stage)()
    except Exception as error:
        emit("error", error_type=type(error).__name__, message=str(error))
        sys.exit(1)
