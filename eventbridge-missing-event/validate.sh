#!/usr/bin/env bash
set -euo pipefail
python lab.py prepare
python lab.py inspect
python lab.py send
python lab.py diagnose
if python lab.py repair; then echo 'Unedited pattern was accepted' >&2; exit 1; fi
python - <<'PY'
import json
from pathlib import Path
p = Path('pattern.json')
pattern = json.loads(p.read_text())
pattern['detail-type'] = ['OrderCreated']
p.write_text(json.dumps(pattern, indent=2) + '\n')
PY
python lab.py repair
python lab.py inspect
python lab.py resend
python lab.py verify
python lab.py cleanup
if python lab.py prepare; then echo 'Corrected starting pattern was accepted' >&2; exit 1; fi
