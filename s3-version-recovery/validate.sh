#!/usr/bin/env bash
set -euo pipefail
python lab.py prepare
python lab.py inspect
python lab.py break
python lab.py diagnose
python - <<'PY'
import json
from pathlib import Path
state = json.loads(Path('.lab/state.json').read_text())
Path('recovery.json').write_text(json.dumps({'version_id': state['bad_version']}) + '\n')
PY
if python lab.py repair; then
  echo 'Expected repair to reject the invalid configuration' >&2
  exit 1
fi
python - <<'PY'
import json
from pathlib import Path
state = json.loads(Path('.lab/state.json').read_text())
Path('recovery.json').write_text(json.dumps({'version_id': state['original_version']}) + '\n')
PY
python lab.py repair
python lab.py verify
python lab.py inspect
python lab.py cleanup
