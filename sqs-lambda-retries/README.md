# SQS + Lambda: break the flow, recover the message

Make Lambda fail, trace SQS retries, and recover a message from the DLQ.
Run the lab locally with AWS Emulator, without an AWS account.

**[English guide](README.en.md) · [Guía en español](README.es.md)**

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

## Get started

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-lambda-retries
```

Choose the [English](README.en.md#set-up-your-environment) or
[Spanish](README.es.md#prepara-tu-entorno) setup guide. Allow about 40 minutes,
plus installation.

- **Linux:** AWS Emulator 1.0.322 and Python with pip/venv, using two terminals.
- **Docker:** run `bash docker-lab.sh` in Bash (WSL on Windows). The image
  includes the emulator, Python, and nano; work in its shell.

## Files

| File | Purpose |
| --- | --- |
| `lab.py` | Stage commands, inspection, and verification through Boto3 |
| `handler.py` | Deliberate failure for `order-poison` |
| `consumer.json` | Configuration you edit to repair the consumer |
| `start-emulator.sh` | Starts the emulator on Linux |
| `docker-lab.sh` | Builds the image and mounts local logs |
| `Dockerfile`, `docker-shell.sh` | Container setup |
| `recorded/` | Logs from the reference runs |
| `tests/test_diagnose.py` | Regression tests for asynchronous diagnosis |

Your full sequence is saved in `.lab/events.jsonl` in this directory on your
computer. Docker mounts `.lab` into the container; the files stay here after
cleanup and container removal. Read them with your editor or:

```bash
cat .lab/events.jsonl
```

`docker-lab.sh` builds the container user with your local UID/GID so the files
remain readable and writable on Linux too. The raw emulator startup log can
contain generated local credentials; review it before sharing.

## Validation

The [updated runner](recorded/2026-11-14-diagnose/) completed the flow with PASS
on AWS Emulator **1.0.322**, Linux aarch64 in Docker, with networking disabled
and a 2 GiB memory limit. The [original run](recorded/README.md) also covers
invalid stage transitions. Both include logs and source hashes.

The native Linux installation has not been tested on a separate host.
Docker pins the emulator version; its base image and OS packages are not pinned.

After installing the Python requirements, run the regression tests from this
directory. They use mocks and require no running emulator:

```bash
python -m unittest discover -s tests -v
```

## En español

Provoca un fallo en Lambda, sigue los reintentos de SQS y recupera el mensaje
de la DLQ. La [guía en español](README.es.md) incluye la preparación en Linux
o Docker y las ocho etapas de la práctica. Los logs quedan en `.lab/events.jsonl`
en tu equipo, incluso después de cerrar el contenedor.
