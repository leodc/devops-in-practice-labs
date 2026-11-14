# Secrets Manager: bring back the working version

Publish a version the consumer rejects, then restore a working version with AWSCURRENT.

The code has not changed, but reading the updated secret breaks the consumer. Reproduce the problem with sample data in AWS Emulator and choose which version to restore.

## Set up your environment

### 1. Clone the repository

If you already have the repository, run git pull from its root and enter this lab directory.

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/secrets-version-rollback
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
cd devops-in-practice-labs/secrets-version-rollback
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

## 1. Create the secret and read it

Create a sample secret and run the consumer validator.

```bash
python lab.py prepare
python lab.py inspect
```

- Find consumer_read with result ACCEPTED and save its version_id.
- Open read_version in lab.py: the consumer expects schema 1 and a nonempty api_key. The log records validation results, never the secret value.

What happens when you read the secret without choosing a version?

GetSecretValue returns the version labeled AWSCURRENT. The ID identifies the version; the label can move.

## 2. Publish the breaking change

Publish a document with schema 2 and token instead of api_key.

```bash
python lab.py publish-bad
python lab.py inspect
```

- Find consumer_read with REJECTED and valid false.
- Compare labels: the new version has AWSCURRENT; the earlier version has AWSPREVIOUS.

Why does Secrets Manager accept a value the application rejects?

The service stores the value; it does not know the format your consumer requires. Here, Python validation fails when it reads the new document.

### Reference trace

```text
{"event": "consumer_read", "result": "ACCEPTED", "stages": ["AWSCURRENT"], "time": "2026-11-14T09:46:29.480843+00:00", "valid": true, "version_id": "ac0e556f-6f04-45e7-ad26-1d3e1a09dd70"}
{"event": "consumer_read", "reason": "consumer_requires_schema_1_and_api_key", "result": "REJECTED", "stages": ["AWSCURRENT"], "time": "2026-11-14T09:46:29.882311+00:00", "valid": false, "version_id": "795b2924-b170-484f-adf0-261c67676152"}
```

## 3. Find a valid version

Read each version by ID and compare validation results.

```bash
python lab.py diagnose
```

- Find version_checked with valid true and copy its version_id.
- Confirm that the current version is still the rejected one.

Is choosing AWSPREVIOUS enough?

AWSPREVIOUS identifies the version that was current before the latest change. Validate its contents before choosing it; the label alone does not tell you whether the consumer can use it.

## 4. Move AWSCURRENT to your chosen version

In recovery.json, replace the value of version_id with the ID that passed validation. Save with Ctrl+O, Enter, then exit with Ctrl+X. Run repair to move the label.

```bash
nano recovery.json
python lab.py repair
python lab.py inspect
```

- Check from_version and to_version in label_moved.
- The valid version should have AWSCURRENT; the rejected one now has AWSPREVIOUS.

Did the rollback create another secret version?

No. UpdateSecretVersionStage moves labels between existing versions. AWSPREVIOUS automatically moves to the version that lost AWSCURRENT.

## 5. Check a fresh read

Read the secret without selecting a version and run the validator again.

```bash
python lab.py verify
```

- Find verification with result PASS, current.valid true, and the recovered version ID.

What if the application had cached the previous value?

This consumer performs a fresh read. Moving AWSCURRENT does not update a value the application already holds in memory; its cache strategy determines when it reads again.

### Reference trace

```text
{"consumer": "fresh_read_without_version_selector", "current": {"stages": ["AWSCURRENT"], "valid": true, "version_id": "ac0e556f-6f04-45e7-ad26-1d3e1a09dd70"}, "event": "verification", "previous": {"stages": ["AWSPREVIOUS"], "valid": false, "version_id": "795b2924-b170-484f-adf0-261c67676152"}, "result": "PASS", "time": "2026-11-14T09:46:30.684885+00:00"}
```

## 6. Clean up and keep the sequence

Delete the sample secret. The traces stay in .lab/events.jsonl on your computer.

```bash
python lab.py cleanup
cat .lab/events.jsonl
```

- Find cleanup_completed and follow the label changes from start to finish.
- Linux: stop terminal A with Ctrl+C. Docker: exit the shell; .lab/events.jsonl remains in the lab directory on your computer.
- If you restarted the emulator mid-lab, run python lab.py reset, then prepare again. Earlier logs are kept.

What evidence explains the recovery?

A rejected read, validation of the chosen version, the AWSCURRENT move, and an accepted fresh read. Version IDs connect the sequence without logging secret contents.

## Recovery verified

You moved AWSCURRENT back to a valid version and confirmed that a fresh consumer read accepts it.

## References

- [AWS Emulator](https://docs.aws.amazon.com/emulator/latest/userguide/what-is-service.html)
- [Secrets Manager · UpdateSecretVersionStage](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_UpdateSecretVersionStage.html)
- [Code and reference traces](https://github.com/leodc/devops-in-practice-labs/tree/main/secrets-version-rollback)
