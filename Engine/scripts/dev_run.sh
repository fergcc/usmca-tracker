#!/usr/bin/env bash
# TMEC Engine — dev run script.
# Runs the full pipeline (search + enrich) with verbose output.
# Usage: bash scripts/dev_run.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENGINE_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="$(dirname "$ENGINE_DIR")"
cd "$DASHBOARD_DIR"

echo "=== TMEC Engine — Dev Run ==="
echo "Dashboard dir: $DASHBOARD_DIR"
echo ""

# Load .env if present (from Engine/.env)
if [ -f "$ENGINE_DIR/.env" ]; then
  set -a
  source "$ENGINE_DIR/.env"
  set +a
  echo "[dev] Loaded $ENGINE_DIR/.env"
fi

# Check Python deps (use Engine venv if available)
PYTHON=python3
if [ -f "$ENGINE_DIR/.venv/bin/python" ]; then
  PYTHON="$ENGINE_DIR/.venv/bin/python"
fi

"$PYTHON" -c "import openai" 2>/dev/null || {
  echo "[dev] Installing dependencies..."
  "$PYTHON" -m pip install -r "$ENGINE_DIR/requirements.txt"
}

# Run engine from Dashboard directory
"$PYTHON" -m Engine.engine run "$@"
