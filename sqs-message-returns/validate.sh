#!/usr/bin/env bash
set -euo pipefail
python lab.py prepare
if python lab.py verify; then echo 'Premature verification accepted' >&2; exit 1; fi
python lab.py receive
if python lab.py ack; then echo 'Deletion before observing redelivery accepted' >&2; exit 1; fi
python lab.py receive
python lab.py ack
python lab.py verify
python lab.py cleanup
