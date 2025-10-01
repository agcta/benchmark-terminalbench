#!/usr/bin/env bash
# Run a batch of additional Terminal-Bench tasks with Grok-4.
#
# Usage:
#   bash scripts/run_additional_tasks.sh
#
# Optional environment overrides:
#   TASK_TRIALS=3 LOG_ROOT=M2_raw_logs MODEL=grok-4 bash scripts/run_additional_tasks.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

TASKS=(
  accelerate-maximal-square
  acl-permissions-inheritance
  adaptive-rejection-sampler
  add-benchmark-lm-eval-harness
  aimo-airline-departures
  amuse-install
  analyze-access-logs
)

TASK_TRIALS=${TASK_TRIALS:-5}
MODEL=${MODEL:-grok-4}
NETWORK_MODE=${NETWORK_MODE:-offline}
LOG_ROOT=${LOG_ROOT:-M2_raw_logs}

for task in "${TASKS[@]}"; do
  echo "========== Running task: ${task} =========="
  python "${REPO_ROOT}/scripts/run_terminal_bench.py" \
    --task-id "${task}" \
    --trials "${TASK_TRIALS}" \
    --model "${MODEL}" \
    --log-dir "${LOG_ROOT}" \
    --network-mode "${NETWORK_MODE}"
done

echo "All tasks finished. Logs stored under ${LOG_ROOT}."
