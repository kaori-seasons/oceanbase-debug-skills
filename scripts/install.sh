#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
tool=""
target=""
extra=()
while (($#)); do
  case "$1" in
    --tool) tool="${2:?--tool needs a value}"; shift 2 ;;
    --target) target="${2:?--target needs a value}"; shift 2 ;;
    --force) extra+=(--force); shift ;;
    *) echo "Usage: install.sh --tool codex|claude-code|cursor|jetbrains --target PATH [--force]" >&2; exit 2 ;;
  esac
done
if [[ -z "$tool" || -z "$target" ]]; then
  echo "--tool and --target are required; no default writes to a global skills directory" >&2
  exit 2
fi
python3 "$script_dir/skill_converter.py" --convert "$tool" --target "$target" ${extra[@]+"${extra[@]}"}
