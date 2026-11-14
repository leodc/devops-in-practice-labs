# Diagnosis regression validation / Validación de diagnose

Real run on 2026-11-14 using the updated runner, AWS Emulator 1.0.322,
Linux aarch64 in Docker, external networking disabled, and a 2 GiB memory cap.
The environment event records the exact runner and handler hashes.

The run completed prepare, send, consume, diagnose, a second diagnose using
saved evidence, repair, redrive, verify (PASS), and cleanup. Three failed
deliveries and successful recovery were observed. The validation changed
consumer.json programmatically; learners edit it with nano.

`events.jsonl` is the unmodified runner output; `handler.log` contains the
original messages from its lambda_log events. Startup logs and credentials
are excluded. The original November 12 evidence remains unchanged one level up.

The seven tests in `tests/test_diagnose.py` separately simulate delayed and
out-of-order logs, empty receives, timeouts, invalid messages, and repeated
diagnosis. Those cases are mocked regression tests, not claims about errors
observed in this emulator run.

Ejecución real del runner corregido con AWS Emulator 1.0.322. Se observaron
los tres fallos, el diagnóstico, la recuperación, PASS y la limpieza.
Las siete pruebas de regresión simulan los retrasos y las recepciones vacías;
no son fallos observados en esta ejecución. Los logs originales del 12 de
noviembre se conservan sin cambios.
