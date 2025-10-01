#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PATH="$REPO_ROOT/.venv"
HARNESS_DIR="$REPO_ROOT/external/lm-evaluation-harness"

if [ ! -d "$VENV_PATH" ]; then
  echo "[ERROR] Virtualenv not found at $VENV_PATH. Run env/setup.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

if [ ! -d "$HARNESS_DIR" ]; then
  git clone https://github.com/EleutherAI/lm-evaluation-harness.git "$HARNESS_DIR"
else
  echo "[INFO] lm-evaluation-harness already present. Pulling latest changes."
  git -C "$HARNESS_DIR" pull --ff-only
fi

python -m pip install -e "$HARNESS_DIR"[openai]

echo "[INFO] Bootstrap complete. Harness ready at $HARNESS_DIR"
