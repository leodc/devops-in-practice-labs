# S3: recover the file you overwrote and deleted

Restore an earlier S3 object version and check that you recovered the right content.

A configuration file was overwritten with a bad value, then deleted. Inspect the versions left behind and restore the working configuration with AWS Emulator.

## Set up your environment

### 1. Clone the repository

If you already have the repository, run git pull from its root and enter this lab directory.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/s3-version-recovery
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
cd devops-in-practice-labs/s3-version-recovery
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

- Use Bash and Docker with Linux containers; on Windows, run these commands in WSL.

Continue in the shell that opens.

## 1. Upload a working configuration

Create a versioned bucket and upload config.json with timeout_seconds set to 30.

```bash
python lab.py prepare
python lab.py inspect
```

- Find versioning: Enabled and the current version_id.
- Find the original SHA-256 to compare with the recovered file later.

What does the version ID identify?

One version of this object. Later writes to the same key receive their own version IDs.

## 2. Overwrite it, then delete it

Replace the timeout with 0, then delete config.json without specifying a version.

```bash
python lab.py break
python lab.py inspect
```

- The current read returns NoSuchKey.
- The history still contains two object versions and a delete marker marked latest.

Did the delete remove the two stored versions?

With versioning enabled, deleting without VersionId adds a delete marker. A GET without a version ID no longer returns the object, but you can still read earlier versions by ID.

## 3. Find the configuration to recover

Read the stored versions and compare their contents.

```bash
python lab.py diagnose
```

- Find timeout_seconds: 30 and copy its version_id.
- Compare it with the version containing timeout_seconds: 0.

Would removing the delete marker recover the working configuration?

It would expose the most recent object version, which contains the bad timeout. Choose the earlier working version instead.

## 4. Restore the chosen version

Set version_id in recovery.json to the working version from diagnose. Save in nano with Ctrl+O, Enter, then exit with Ctrl+X.

```bash
nano recovery.json
python lab.py repair
```

- Find source_version and new_version in version_restored.
- The helper rejects the version with the invalid timeout before copying it.

Why does the restored object have a new version ID?

CopyObject reads the explicitly selected source version and writes a new version at the same key. The earlier versions and delete marker remain in the history.

## 5. Check the restored file

Read the current object and compare it with the original content.

```bash
python lab.py verify
python lab.py inspect
cat .lab/recovered-config.json
```

- Look for matches_original: true and the original SHA-256.
- The history now has four entries: the two earlier versions, the delete marker, and the restored version.

Does a new version ID prove you recovered the right content?

The new version ID shows a new write occurred. The content hash checks that the current object contains exactly the original bytes.

### Reference trace

```text
{"error_code": "NoSuchKey", "event": "current_object_missing", "http_status": 404, "time": "2026-11-14T09:46:08.854733+00:00"}
{"event": "version_restored", "new_version": "ba240be8196984c3ebbbbdece4ce530b", "source_version": "014eff17fab3d44869c86a6beec09942", "time": "2026-11-14T09:46:09.255350+00:00"}
{"event": "recovery_verified", "file": ".lab/recovered-config.json", "history_entries": 4, "matches_original": true, "sha256": "bb05bf2c57c1f5aa3c5fb93c7e05b71e5e43848f584896c8047c16df3c2563a9", "time": "2026-11-14T09:46:09.434978+00:00", "version_id": "ba240be8196984c3ebbbbdece4ce530b"}
```

## 6. Remove the bucket, keep the evidence

Delete every version and delete marker, then remove the bucket.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Follow the version IDs from upload through recovery in events.jsonl.
- Keep .lab/recovered-config.json to inspect the recovered content after the emulator stops.
- Linux: stop terminal A with Ctrl+C. Docker: exit the shell. The files in .lab remain on your computer.
- If you restarted the emulator mid-lab, run python lab.py reset, then prepare again. Earlier logs are kept.

Why does cleanup explicitly delete versions?

Deleting only the current key would add another delete marker. A versioned bucket must have its stored versions and delete markers removed before the bucket can be deleted.

## The working configuration is current again

You recovered the selected version, verified its content, and kept a local record of the sequence.

## References

- [Lab source on GitHub ↗](https://github.com/leodc/devops-in-practice-labs/tree/main/s3-version-recovery)
- [S3 versioning ↗](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [Restoring object versions ↗](https://docs.aws.amazon.com/AmazonS3/latest/userguide/RestoringPreviousVersions.html)
