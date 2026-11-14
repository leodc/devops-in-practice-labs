# Reference run / Ejecución de referencia

Executed on 2026-11-14 with AWS Emulator 1.0.322, Boto3 1.40.75,
Linux aarch64 in Docker on macOS. The environment event records exact source
hashes. Native installation on a separate Linux host was not tested.

Run `bash docker-lab.sh bash validate.sh` to reproduce the automated check.
The trace includes two expected guard errors: verification before deletion,
and deletion before observing redelivery. The same message was received with
counts 1 and 2, then received again with count 3 to obtain a fresh receipt
handle for deletion. Verification passed and cleanup completed. These are
helper observations of real emulator API calls, not SQS service logs.

The automation took about eight seconds after emulator startup. The five-minute
estimate allows time to read, pause, and compare results; initial setup is extra.
Logs remain in `.lab/events.jsonl` on the host after the container is removed.
Startup logs and credentials are not included.

Ejecución real: mismo mensaje recibido dos veces, nueva recepción para borrarlo,
verificación PASS y limpieza. La traza conserva dos rechazos esperados por
intentar avanzar fuera de orden. Los cinco minutos incluyen leer y comparar;
la preparación inicial del entorno se realiza antes.
