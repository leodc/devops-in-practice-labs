# Recorded run

Captured on 2026-11-14 with `bash docker-lab.sh python validate.py` on macOS using Docker's Linux arm64 environment, AWS Emulator 1.0.322 and Boto3 1.40.75. Native Linux installation was not exercised on a separate host.

`events.jsonl` contains the helper's actual API observations and validation failures expected by `validate.py`. It starts at the final run's environment event and ends after table deletion. The complete local file also contains an intentional `verify` call before preparation; it is omitted here because it precedes the environment event.

The environment event records SHA-256 hashes of the exact Python helper, validation script, initial writer configuration, requirements, and Dockerfile. `writer_applied` records the edited configuration hash. No timestamps, outcomes, or IDs in this capture were rewritten. No raw emulator startup logs or credential files are included.

Tested image: `sha256:8c5824bb7b7a6ff5b898b7d7b0d8b696d2784dfe85fb58320bf239464ba21e7f` (linux/arm64).

Verified: two accepted writes leave value 1; a conditional stale write returns `ConditionalCheckFailedException`; an explicit reread and recalculation yields value 2/version 2; invalid stage transitions and invalid configuration fail; editing the configuration does not apply it until `repair`; table cleanup completes while host logs remain.
