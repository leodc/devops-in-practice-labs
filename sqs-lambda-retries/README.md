# SQS + Lambda: break the flow, recover the message

Make Lambda fail, trace SQS retries, and recover a message from the DLQ.
The first local practice lab from **DevOps in Practice**: real code, real logs,
no AWS account required.

**[English guide](README.en.md) · [Guía en español](README.es.md)**

## The experiment

```text
order-ok ──────┐
              ├── SQS ── Lambda
order-poison ──┘            │
                  3 failed deliveries
                           ↓
                          DLQ
                           │
                   repair → redrive
                           ↓
                    SQS ── Lambda ✓
```

Eight deliberate stages: prepare, send, consume, diagnose, repair, redrive,
verify, and cleanup. Stop to inspect between changes. The Python helper uses
Boto3 and explicit loopback endpoints; the browser does not run the lab.
Retries proceed automatically once consumption is enabled. Recovery requires
an explicit configuration edit and redrive.

## Start here

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-lambda-retries
```

Choose the [English](README.en.md#set-up-your-environment) or [Spanish](README.es.md#prepara-tu-entorno)
setup guide before running the stages.

- **Linux:** install AWS Emulator 1.0.322 and Python with venv/pip.
  Use one terminal for the emulator and another for the lab.
- **Docker (macOS / Windows / Linux):** the image installs AWS Emulator 1.0.322
  and provides one working shell. AWS Emulator has no native macOS or Windows binary.
- **About 40 minutes**, plus installation. Git is needed to clone the repository. No AWS account or personal AWS credentials.

## Files you will use

| File | Purpose |
| --- | --- |
| `lab.py` | Boto3 calls, stage guards, observation and verification |
| `handler.py` | Deterministic failure for `order-poison` |
| `consumer.json` | Configuration you edit before applying the repair |
| `start-emulator.sh` | Native Linux startup on loopback port 19397 |
| `Dockerfile`, `docker-shell.sh` | Isolated Linux environment |
| `recorded/` | Real reference-run events and original handler log messages |

Your run writes evidence into `.lab/events.jsonl`. This directory is ignored by
Git. Never commit local credentials or the raw emulator startup log.

## What was validated

The full flow passed on AWS Emulator **1.0.322**, Linux aarch64 inside a Docker
container from macOS, with external networking disabled during execution.
The reference run includes three failed deliveries, DLQ inspection, repair,
redrive, successful processing, and cleanup. Six invalid transitions were
also rejected. See [recorded evidence](recorded/README.md) for provenance,
source hashes, and deliberate guard-test errors.

The standalone native Linux installation was not tested on a separate host.
This experiment does not verify production IAM enforcement, scaling, durability,
or timing. Emulator 1.0.322 preserves message identity on redrive, while AWS
documents new IDs; the guides explain that observed fidelity gap.

## En español

Provoca un fallo en Lambda, sigue los reintentos de SQS y rescata el mensaje de
la DLQ. Nuestro primer lab local: código real, logs reales y sin cuenta de AWS.
Sigue la [guía completa en español](README.es.md), inspecciona cada etapa y
contrasta tus resultados con la evidencia de referencia.

## Version and regression checks

The Dockerfile pins AWS Emulator to **1.0.322**, the version in the recorded
run. On Linux, install the same version using the
[official versioned package instructions](https://docs.aws.amazon.com/emulator/latest/userguide/versioning.html)
and confirm it with `aws-emulator --version`. The container base and OS packages
are not pinned; this fixes the emulator version, not a byte-identical image.

After installing the Python requirements, run the asynchronous diagnosis tests
from this lab directory. They use mocks and virtual time, without an emulator
or AWS account:

```bash
python -m unittest discover -s tests -v
```
