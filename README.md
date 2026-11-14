# DevOps in Practice Labs

Hands-on labs from [DevOps in Practice](https://leocasta.com/labs/).
Each lab lives in its own directory with its code, setup instructions, and
English and Spanish guides. Follow the stages, inspect the results, and keep
your own evidence.

## Labs

| Directory | Practice | Guides |
| --- | --- | --- |
| [`sqs-message-returns/`](sqs-message-returns/) | Start here: receive the same SQS message twice, then delete it. Five minutes after setup. | [English](sqs-message-returns/README.en.md) · [Español](sqs-message-returns/README.es.md) |
| [`sqs-lambda-retries/`](sqs-lambda-retries/) | Make Lambda fail, trace SQS retries, and recover a message from the DLQ using AWS Emulator. | [English](sqs-lambda-retries/README.en.md) · [Español](sqs-lambda-retries/README.es.md) |
| [`s3-version-recovery/`](s3-version-recovery/) | Recover the correct version of an overwritten and deleted S3 object. | [English](s3-version-recovery/README.en.md) · [Español](s3-version-recovery/README.es.md) |
| [`dynamodb-lost-update/`](dynamodb-lost-update/) | Reproduce a lost update, reject stale writes, and retry from a fresh read. | [English](dynamodb-lost-update/README.en.md) · [Español](dynamodb-lost-update/README.es.md) |
| [`eventbridge-missing-event/`](eventbridge-missing-event/) | Diagnose an accepted event that misses its rule and verify delivery to SQS. | [English](eventbridge-missing-event/README.en.md) · [Español](eventbridge-missing-event/README.es.md) |
| [`secrets-version-rollback/`](secrets-version-rollback/) | Recover a secret version the consumer accepts by moving AWSCURRENT. | [English](secrets-version-rollback/README.en.md) · [Español](secrets-version-rollback/README.es.md) |

## Get started

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-message-returns
```

Read the lab's setup guide before running commands. Run each lab from its own
directory so its dependencies, configuration, and evidence stay together.

## Repository structure

```text
devops-in-practice-labs/
├── sqs-message-returns/
├── sqs-lambda-retries/
├── s3-version-recovery/
├── dynamodb-lost-update/
├── eventbridge-missing-event/
└── secrets-version-rollback/
```

New labs belong in a directory named after their lab ID. Include the code,
dependencies, setup and cleanup instructions, and guides in both languages.
Add a link to the lab in the table above. Each lab documents its own requirements.

## En español

Labs de práctica de [DevOps in Practice](https://leocasta.com/es/labs/).
Cada directorio contiene el código y las guías de un lab. Clona el repositorio
una vez, entra en el directorio del ejercicio y sigue su guía de preparación.
Inspecciona los resultados entre etapas y conserva tu propia evidencia.
