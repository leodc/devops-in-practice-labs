# Reference run / Ejecución de referencia

Executed on 2026-11-14 with AWS Emulator 1.0.322 and Boto3 1.40.75,
Linux aarch64 in Docker on macOS. The `environment` event records the
exact runner hash. Native installation on a separate Linux host was not tested.

`events.jsonl` is the unmodified helper trace, including two expected guard
errors: repair before diagnosis, and repair without selecting a valid version.
The flow completed with PASS and cleanup. `bash docker-lab.sh bash validate.sh` automates this check;
learners select the version manually in their editor. These are client-side
observations of real emulator API calls and the Python consumer validator,
not service logs. Secret values, startup logs, and credentials are excluded.

Ejecución real con PASS y limpieza. La traza conserva dos errores esperados:
reparar antes del diagnóstico y reparar sin elegir una versión válida.
Los eventos registran respuestas del emulador y validación del consumidor;
no contienen valores del secreto ni credenciales.
