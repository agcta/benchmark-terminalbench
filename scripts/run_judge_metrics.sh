#!/usr/bin/env bash
# Run the Grok-4 judge across every post-agent transcript we have collected.
#
# Usage:
#   bash scripts/run_judge_metrics.sh
#
# Optional environment overrides:
#   JUDGE_MODEL=grok-4 METRICS_DIR=M3_outputs LOG_ROOT=benchmarks/tasks/... bash scripts/run_judge_metrics.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

JUDGE_MODEL=${JUDGE_MODEL:-grok-4}
METRICS_DIR=${METRICS_DIR:-M3_outputs}
LOG_ROOT=${LOG_ROOT:-$REPO_ROOT/benchmarks/tasks/terminal-bench/M2_raw_logs}
CONFIG_ROOT=${CONFIG_ROOT:-$REPO_ROOT/configs/metrics}

mkdir -p "${METRICS_DIR}"

# Mapping from task_id to optional config file. Add entries as bespoke configs land.
map_task_config() {
  case "$1" in
    conda-env-conflict-resolution)
      printf '%s\n' "${CONFIG_ROOT}/conda-env-conflict-resolution.json"
      ;;
    *)
      printf '\n'
      ;;
  esac
}

POST_AGENT_LOGS=$(find "$LOG_ROOT" -path '*panes/post-agent.txt' | sort)

if [[ -z "$POST_AGENT_LOGS" ]]; then
  echo "No post-agent transcripts found under ${LOG_ROOT}" >&2
  exit 1
fi

IFS=$'\n'
for log in $POST_AGENT_LOGS; do
  log=${log%$'\r'}
  trial_dir=$(basename "$(dirname "$(dirname "$(dirname "$log")")")")
  task_id=$(echo "$trial_dir" | sed 's/_trial.*//')

  output_path="${METRICS_DIR}/${trial_dir}.metrics.json"
  echo "Judging ${task_id} / ${trial_dir}"

  config_path=$(map_task_config "$task_id")
  if [[ -n "$config_path" && -f "$config_path" ]]; then
    python "${REPO_ROOT}/scripts/M3_eval_metrics.py" \
      --log-file "$log" \
      --config "$config_path" \
      --output "$output_path" \
      --judge-model "$JUDGE_MODEL"
  else
    python "${REPO_ROOT}/scripts/M3_eval_metrics.py" \
      --log-file "$log" \
      --output "$output_path" \
      --judge-model "$JUDGE_MODEL"
  fi
done

echo "Aggregating results..."
python "${REPO_ROOT}/scripts/aggregate_metrics.py" --output "${REPO_ROOT}/reports/M3_Grok4_Diagnosis.json"

echo "Done. See ${REPO_ROOT}/reports/M3_Grok4_Diagnosis.json"
