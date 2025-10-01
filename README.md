# Grok-4 Terminal-Bench Meta-Evaluation Sprint

This repository now targets the 48-hour Agentic Policy evaluation sprint. The previous HumanEval workflow has been archived. The new goal is to baseline xAI's Grok-4 model on Terminal-Bench, critique benchmark design, and deliver enhanced evaluation metrics.

## Repository Layout

- `infra/M1_config.yaml` – Azure DevOps-style pipeline template for auditable Terminal-Bench runs.
- `benchmarks/tasks/` – placeholder for the Terminal-Bench repository (clone or add as submodule).
- `benchmarks/baseline/`, `benchmarks/analysis/` – storage for raw logs and metric outputs.
- `reports/` – milestone artefacts (task selection, baseline metrics, diagnosis, final report).
- `scripts/` – automation scripts (`run_terminal_bench.py`, `M3_eval_metrics.py` forthcoming).

## Quickstart (Milestone M1)

1. Clone Terminal-Bench into `benchmarks/tasks/terminal-bench`:
   ```bash
   git submodule add https://github.com/laude-institute/terminal-bench.git benchmarks/tasks/terminal-bench
   ```
2. Ensure Docker is available and run a sample task to verify the harness.
3. Execute the helper script (requires `OPENAI_API_KEY` or `XAI_API_KEY` for Grok access):
   ```bash
   source .venv/bin/activate
   export XAI_API_KEY=...
   python scripts/run_terminal_bench.py --task-id dependency-hell-2 --trials 1 --model grok-4
   ```
4. Use `infra/M1_config.yaml` as the basis for the audit pipeline.

## Planned Milestones

- **M1**: Environment setup + task selection (completed scaffold only).
- **M2**: Grok-4 baseline runs (command logs per trial).
- **M3**: Implement PR/CA/SRS metrics and analyze baseline logs.
- **M4**: Create `task-id-X-revised` with injected hard constraints and enhanced logging.
- **M5**: Validate revised task, collect new metrics.
- **M6**: Produce final report plus reproducibility package.

## Notes

- Keep API keys in environment variables; pipeline template enforces command logging and security audits.
- Future scripts will populate `reports/` with JSON diagnostics.

