#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Match the host user so the bind-mounted logs remain readable and writable.
mkdir -p .lab
docker build \
  --build-arg "LAB_UID=$(id -u)" \
  --build-arg "LAB_GID=$(id -g)" \
  -t sqs-message-returns-practice .

terminal_flags=(-i)
if [[ -t 0 && -t 1 ]]; then
  terminal_flags+=(-t)
fi

exec docker run --rm "${terminal_flags[@]}" \
  --name sqs-message-returns-practice \
  --network none --memory=2g --memory-swap=2g \
  --mount "type=bind,src=$PWD/.lab,dst=/opt/lab/.lab" \
  sqs-message-returns-practice "$@"
