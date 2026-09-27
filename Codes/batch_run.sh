#!/usr/bin/env bash
# Compatibility entry point. The implementation lives in batch_run.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="${PYTHON_CMD:-python3}"

exec "${PYTHON_CMD}" "${SCRIPT_DIR}/batch_run.py" "$@"
