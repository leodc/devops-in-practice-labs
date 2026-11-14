# DevOps in Practice Labs

Hands-on labs from [DevOps in Practice](https://leocasta.com/labs/).
Each lab lives in its own directory with its code, setup instructions, and
English and Spanish guides. Follow the stages, inspect the results, and keep
your own evidence.

## Labs

| Directory | Practice | Guides |
| --- | --- | --- |
| [`sqs-lambda-retries/`](sqs-lambda-retries/) | Make Lambda fail, trace SQS retries, and recover a message from the DLQ using AWS Emulator. | [English](sqs-lambda-retries/README.en.md) · [Español](sqs-lambda-retries/README.es.md) |

## Get started

```bash
git clone https://github.com/leodc/devops-in-practice-labs.git
cd devops-in-practice-labs/sqs-lambda-retries
```

Read the lab's setup guide before running commands. Run each lab from its own
directory so its dependencies, configuration, and evidence stay together.

## Repository structure

```text
devops-in-practice-labs/
├── README.md
└── sqs-lambda-retries/
    ├── README.md
    ├── README.en.md
    ├── README.es.md
    ├── lab.py
    ├── handler.py
    └── recorded/
```

New labs belong in a directory named after their lab ID. Include the code,
dependencies, setup and cleanup instructions, and guides in both languages.
Add a link to the lab in the table above. Each lab documents its own requirements.

## En español

Labs de práctica de [DevOps in Practice](https://leocasta.com/es/labs/).
Cada directorio contiene el código y las guías de un lab. Clona el repositorio
una vez, entra en el directorio del ejercicio y sigue su guía de preparación.
Inspecciona los resultados entre etapas y conserva tu propia evidencia.
