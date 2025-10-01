#!/usr/bin/env python
"""Baseline HumanEval+ runner for ART-H sprint.

Wraps the lm-evaluation-harness CLI so we can run GPT-5 via the OpenAI API
and capture artifacts in a predictable local directory structure.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_CONFIG = Path("configs/models/openai_gpt5_baseline.yaml")


def dict_to_model_args(params: Dict[str, Any]) -> str:
    """Convert a dictionary of model parameters into the harness CLI format."""
    parts = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = str(value).lower()
        parts.append(f"{key}={value}")
    return ",".join(parts)


def _copy_latest(run_dir: Path, pattern: str, destination: Path) -> Optional[Path]:
    candidates = sorted(run_dir.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    latest = candidates[0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if latest != destination:
        shutil.copy(latest, destination)
    return destination


def run_lm_eval(config: Dict[str, Any], dry_run: bool) -> Path:
    eval_cfg = config["eval"]
    artifacts_dir = Path(eval_cfg.get("artifacts_dir", "artifacts"))
    run_id = eval_cfg.get("run_id", "baseline")
    run_dir = artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    model_args = dict_to_model_args(config.get("model_args", {}))

    cmd = [
        sys.executable,
        "-m",
        "lm_eval",
        "--model",
        config["model"],
        "--tasks",
        eval_cfg.get("task", "humaneval"),
        "--num_fewshot",
        str(eval_cfg.get("num_fewshot", 0)),
        "--batch_size",
        str(eval_cfg.get("batch_size", 1)),
        "--limit",
        str(eval_cfg.get("limit", 20)),
        "--output_path",
        str(run_dir),
        "--log_samples",
        "--confirm_run_unsafe_code",
    ]

    if eval_cfg.get("apply_chat_template"):
        cmd.append("--apply_chat_template")

    if model_args:
        cmd.extend(["--model_args", model_args])

    if dry_run:
        print("[DRY-RUN] lm-evaluation-harness command:")
        print(" ".join(cmd))
        return run_dir

    print("[INFO] Launching lm-evaluation-harness...")
    env = os.environ.copy()
    if "OPENAI_API_KEY" not in env:
        raise RuntimeError("OPENAI_API_KEY is not set in the environment.")
    # Required to acknowledge Hugging Face's code execution warning when using
    # the HumanEval task (which executes model generated code in a sandbox).
    env.setdefault("HF_ALLOW_CODE_EVAL", "1")

    subprocess.run(cmd, check=True, env=env)

    dataset = eval_cfg.get("task", "humaneval")
    results_path = _copy_latest(run_dir, "results*.json", run_dir / "results.json")
    samples_path = _copy_latest(
        run_dir,
        f"samples_{dataset}*.jsonl",
        run_dir / f"samples_{dataset}.jsonl",
    )
    if results_path is None:
        raise FileNotFoundError(
            f"Unable to locate results JSON in {run_dir}. Harness layout may have changed."
        )
    if samples_path is None:
        print(
            f"[WARN] No samples file matching samples_{dataset}*.jsonl found in {run_dir}."
        )

    print(f"[INFO] Harness evaluation complete. Results at {results_path}")
    return run_dir


def summarize_results(run_dir: Path) -> None:
    results_path = run_dir / "results.json"
    if not results_path.exists():
        print(f"[WARN] results.json missing in {run_dir}; skipping summary")
        return

    with results_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    task = payload.get("configs", {}).get("tasks", ["humaneval"])[0]
    task_results = payload.get("results", {}).get(task, {})
    pass_at_1 = task_results.get("pass@1")
    if pass_at_1 is None:
        for key, value in task_results.items():
            if key.startswith("pass@1"):
                pass_at_1 = value
                break
    if pass_at_1 is None:
        print(json.dumps(payload, indent=2))
        raise RuntimeError("Unable to parse pass@1 from results.json")

    print(f"[INFO] Baseline Pass@1 on {task}: {pass_at_1:.3f}")
    print(f"[INFO] Raw harness payload stored at {results_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline ART-H evaluation")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to YAML config")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    with args.config.open("r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp)

    run_dir = run_lm_eval(config, dry_run=args.dry_run)
    if not args.dry_run:
        summarize_results(run_dir)


if __name__ == "__main__":
    main()
