"""Exercise the real emulator, including rejected stage/configuration transitions."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "writer.json"


def run(stage, failure=None):
    result = subprocess.run([sys.executable, "lab.py", stage], cwd=ROOT, text=True, capture_output=True)
    print(result.stdout, end="")
    if failure:
        assert result.returncode != 0 and failure in result.stdout, (stage, result.stdout, result.stderr)
    else:
        assert result.returncode == 0, (stage, result.stdout, result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]


original = CONFIG.read_text()
try:
    CONFIG.write_text('{\n  "check_version": false\n}\n')
    run("verify", "Expected stage")
    run("prepare")
    run("prepare", "session exists")
    run("retry", "Expected stage")
    run("collide")
    run("collide", "Expected stage")
    run("diagnose")
    run("repair", "Set check_version to true")
    CONFIG.write_text('{"check_version": "true"}\n')
    run("repair", "must contain only")
    CONFIG.write_text('{"check_version": true}\n')
    inspection = next(row for row in run("inspect") if row["event"] == "inspection")
    assert inspection["file_writer"]["check_version"] is True
    assert inspection["applied_writer"]["check_version"] is False
    run("repair")
    run("replay")
    run("verify", "Expected stage")
    run("replay", "Expected stage")
    run("retry")
    run("retry", "Expected stage")
    run("verify")
    run("inspect")
    run("cleanup")
    assert not (ROOT / ".lab/state.json").exists()
    assert (ROOT / ".lab/events.jsonl").exists()
    print("PASS: lost update, stale rejection, recalculated retry, phase/config guards, cleanup, retained logs")
finally:
    CONFIG.write_text(original)
