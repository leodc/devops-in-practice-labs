#!/usr/bin/env bash
set -euo pipefail
python lab.py prepare
python lab.py inspect
if python lab.py repair; then echo 'repair accepted out of order' >&2; exit 1; fi
python lab.py publish-bad
python lab.py inspect
python lab.py diagnose
if python lab.py repair; then echo 'repair accepted missing selection' >&2; exit 1; fi
python - <<'PY'
import json
from pathlib import Path
state = json.loads(Path('.lab/state.json').read_text())
Path('recovery.json').write_text(json.dumps({'version_id': state['good_version']}) + '\n')
PY
python lab.py repair
python lab.py inspect
python lab.py verify
python lab.py cleanup
