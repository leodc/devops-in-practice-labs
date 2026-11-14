# Reference execution

Executed with `bash docker-lab.sh bash validate.sh` on 2026-11-14 using AWS Emulator 1.0.322 and Boto3 1.40.75 inside a Linux aarch64 container on macOS. Native installation on a separate Linux host was not exercised.

`events.jsonl` contains the unmodified JSONL observations emitted by the Python helper during real API calls. These are client observations, not S3 server access logs. The `error` event is the expected negative test: attempting to restore the configuration whose timeout is zero.

`recovered-config.json` is the downloaded current object after recovery. `provenance.json` records the command and source hashes. Emulator startup output and generated credentials are not included.
