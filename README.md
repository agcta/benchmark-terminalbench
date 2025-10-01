# Benchmarking Grok-4 on Terminal-Bench

This repository contains code to analyse Grok-4 on Terminal-Bench, introduce diagnostic metrics, and ship a revised task that stresses long-context policy adherence. The repo is organised to support reproducible experiments, detailed logging, and post-hoc analysis.

## Repository Layout

```
.
├── M2_raw_logs/                     # Baseline Grok-4 runs (original tasks)
├── M3_outputs/                      # Metric JSONs produced by the judge pipeline
├── M4_raw_logs/                     # Revised-task trial logs (real + synthetic)
├── benchmarks/
│   ├── tasks/
│   │   ├── terminal-bench/          # Upstream benchmark checkout (tasks + harness)
│   │   │   ├── tasks/               # >250 official task directories
│   │   │   ├── M2_raw_logs/         # Harness-generated run artifacts (original)
│   │   │   └── M4_raw_logs/         # Harness artifacts for revised tasks
│   │   └── task-id-X-revised/       # Local copy used to craft long-context prompts
│   └── analysis/, baseline/         # Notes and spreadsheets (optional)
├── configs/                         # Metric configs (forbidden commands, etc.)
├── scripts/                         # Utilities for running tasks and aggregating metrics
├── infra/                           # YAML pipeline templates and bootstrap scripts
├── reports/                         # Aggregated summaries (e.g., `M3_Grok4_Diagnosis.json`)
├── README_repo.md                   # This document
└── requirements.txt                 # Python package requirements
```

Key scripts:
- `scripts/run_terminal_bench.py` – Wrapper around the T-Bench CLI to run a task with Grok-4, capture manifests, and drop logs into `M*_raw_logs/`.
- `scripts/M3_eval_metrics.py` – Computes CA/PR/SRS metrics for a single command log (heuristic or judge-assisted depending on config).
- `scripts/run_judge_metrics.sh` – Batch driver to evaluate all transcripts with Grok-4-as-a-judge and produce per-trial metrics.
- `scripts/aggregate_metrics.py` – Collates per-trial metrics into summary JSON reports.

## Prerequisites

1. **System Requirements**
   - macOS or Linux host capable of running Docker (Intel or Apple Silicon).
   - Python 3.9+ (the repo includes `.venv/` but you may prefer creating your own venv).
   - Docker Engine and Compose (T-Bench tasks are containerised).
   - `uv` (optional) if you follow the official T-Bench dependency workflow.

2. **Credentials**
   - Grok/X.ai API key exported as 'XAI_API_KEY` (the wrapper mirrors it to `GROK_API_KEY`).

3. **Python Dependencies**
   Install repo requirements (preferably in a fresh virtual environment):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Terminal-Bench Submodule**
   The harness lives under `benchmarks/tasks/terminal-bench/`. Ensure submodules or vendored files are present. If starting from scratch:
   ```bash
   git clone https://github.com/laude-institute/terminal-bench.git benchmarks/tasks/terminal-bench
   ```

## Running Baseline Tasks (M2)

1. **Set API credentials**
   ```bash
   export X_API_KEY=xai-...
   export TB_NETWORK_MODE=offline  # optional; `run_terminal_bench.py` sets this
   ```

2. **Run a baseline task**
   ```bash
   python scripts/run_terminal_bench.py \
     --task-id conda-env-conflict-resolution \
     --trials 5 \
     --model grok-4 \
     --log-dir M2_raw_logs \
     --network-mode offline
   ```
   Example Outputs:
   - Manifest: `M2_raw_logs/conda-env-conflict-resolution_<timestamp>_manifest.json`
   - Harness logs: `benchmarks/tasks/terminal-bench/M2_raw_logs/runs_conda-env-conflict-resolution_<timestamp>/`
   - Per-trial stdout: `M2_raw_logs/conda-env-conflict-resolution_trialN_<timestamp>.log`

3. **Inspect results**
   Each run directory contains `results.json`, `run.log`, `agent.cast`, and `tests.cast` for post-mortem analysis.

## Revising the Task (M4)

1. **Edit Task Narrative**
   - Long-context prompt at `benchmarks/tasks/terminal-bench/tasks/conda-env-conflict-resolution-revised/task.yaml:2` emphasises hidden constraints.
   - Ensure Dockerfiles/run-tests remain aligned with upstream expectations.

2. **Synthetic vs. Real Trials**
   - Real trial logs live in `M4_raw_logs/` (e.g., `conda-env-conflict-resolution-revised_trial1_20250930181911.log`).
   - Synthetic bundle (plausible failure trace) located under `benchmarks/tasks/terminal-bench/M4_raw_logs/runs_conda-env-conflict-resolution-revised_20250930190042/`.

3. **Run the Revised Task**
   ```bash
   python scripts/run_terminal_bench.py \
     --task-id conda-env-conflict-resolution-revised \
     --model grok-4 \
     --trials 1 \
     --log-dir M4_raw_logs \
     --network-mode offline
   ```

## Metrics Calculation (M3 & M4)

### Single Log Evaluation
```bash
python scripts/M3_eval_metrics.py \
  --log-file M4_raw_logs/conda-env-conflict-resolution-revised_trial1_20250930181911_synthetic_agent.log \
  --config configs/metrics/conda-env-conflict-resolution.json \
  --output M4_raw_logs/conda-env-conflict-resolution-revised_trial1_20250930181911_synthetic_agent.metrics.json
```
This computes:
- `constraint_adherence`
- `process_redundancy`
- `selective_reasoning_failure_rate`

### Batch Judge Execution
1. **Generate per-trial metrics**
   ```bash
   bash scripts/run_judge_metrics.sh \
     JUDGE_MODEL=grok-4 \
     LOG_ROOT=benchmarks/tasks/terminal-bench/M2_raw_logs \
     METRICS_DIR=M3_outputs
   ```
2. **Review aggregated report**
   - `reports/M3_Grok4_Diagnosis.json` summarises CA/PR/SRS and pass@1 per task.

## Aggregating & Reporting

- `scripts/aggregate_metrics.py` can be invoked directly to combine metrics from any directory into a single JSON summary.
- `final_report.md` documents the narrative findings and references relevant artifacts.

## Replication Checklist

1. Clone repo with submodules (`terminal-bench`).
2. Install Python deps (`pip install -r requirements.txt`).
3. Export Grok API key (`XAI_API_KEY`).
4. Run baseline tasks with `scripts/run_terminal_bench.py` (log to `M2_raw_logs`).
5. Run revised tasks (log to `M4_raw_logs`).
6. Execute `scripts/M3_eval_metrics.py` on command logs (or `run_judge_metrics.sh` for batch evaluation).
7. Aggregate metrics with `scripts/aggregate_metrics.py`.
8. Generate or update narrative in `final_report.md`.

## Frequently Used Paths

- **Baseline success evidence:** `benchmarks/tasks/terminal-bench/M2_raw_logs/runs_conda-env-conflict-resolution_20250930025617/conda-env-conflict-resolution_trial4_20250930025617/results.json`
- **Revised task prompt:** `benchmarks/tasks/terminal-bench/tasks/conda-env-conflict-resolution-revised/task.yaml`
- **metrics for long context synthetic task:** `M4_raw_logs/conda-env-conflict-resolution-revised_trial1_20250930181911_synthetic_agent.metrics.json`
- **command trace for synthetic long context task** `M4_raw_logs/conda-env-conflict-resolution-revised_trial1_20250930181911_synthetic_agent.log`
- **harness bundle for synthetic long context task:** `benchmarks/tasks/terminal-bench/M4_raw_logs/runs_conda-env-conflict-resolution-revised_20250930190042/`

## Troubleshooting

- **Missing API key:** `scripts/run_terminal_bench.py` aborts with “XAI API key missing…”; set `XAI_API_KEY`.
- **Forbidden commands not detected:** ensure `configs/metrics/conda-env-conflict-resolution.json` lists the right patterns, or edit localized copies under `resources/`.
- **Metrics script fails:** verify the log path is reachable and the file contains command prompts (lines starting `root@...#`).
- **Docker permission errors:** confirm your user is in the `docker` group or prefix commands with `sudo` if necessary.

## Extending the Repo

- Add new revised tasks under `benchmarks/tasks/task-id-Y-revised/`, then copy into `terminal-bench/tasks/` when ready.
- Update `scripts/run_judge_metrics.sh`’s `map_task_config` function to point to new metric configs.
- Store additional aggregated outputs under `reports/` for easy reference in future deliverables.


