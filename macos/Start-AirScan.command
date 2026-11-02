#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
python_bin=/opt/homebrew/bin/python3.12
if [ ! -x "$python_bin" ]; then
  echo 'Run bash macos/setup.sh first.' >&2
  exit 1
fi
exec "$python_bin" "$project_dir/airscan_bridge.py"
