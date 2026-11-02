#!/bin/bash
set -euo pipefail
if [ "$(uname -s)" != Darwin ]; then
  echo 'Run this script on macOS.' >&2
  exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo 'Install Homebrew from https://brew.sh, then rerun this script.' >&2
  exit 1
fi
if [ "$(uname -m)" = arm64 ] && [ "$(brew --prefix)" != /opt/homebrew ]; then
  echo 'Use native Apple Silicon Homebrew at /opt/homebrew.' >&2
  exit 1
fi
brew install sane-backends python@3.12
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
python_bin="$(brew --prefix)/bin/python3.12"
"$python_bin" -m pip install --target "$project_dir/.runtime/python" -r "$project_dir/requirements.txt"
if [ ! -f "$project_dir/.runtime/firmware/cism216.fw" ]; then
  firmware_path="${1:-}"
  if [ -z "$firmware_path" ]; then
    echo 'Select your own OpticSlim 1200 Cism216.fw firmware file.'
    firmware_path="$(osascript -e 'POSIX path of (choose file with prompt "选择 OpticSlim 1200 原驱动中的 Cism216.fw 固件")')"
  fi
  "$python_bin" "$project_dir/opticslim.py" import-firmware "$firmware_path" \
    --source-info 'User-supplied OpticSlim 1200 original driver firmware on macOS'
fi
"$python_bin" "$project_dir/opticslim.py" doctor
printf '\nSetup complete. Connect the scanner, then run:\n  bash macos/Start-AirScan.command\n'
