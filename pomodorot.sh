#!/usr/bin/env bash
# Launcher for the pomodorot pomodoro app.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /home/ehud/miniforge3/bin/python3 "$PROJECT_DIR/main.py" "$@"
