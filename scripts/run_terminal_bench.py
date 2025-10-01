#!/usr/bin/env python
"""Orchestrate Terminal-Bench runs with Grok-4.

This wrapper is referenced by infra/M1_config.yaml and can be reused manually:

python scripts/run_terminal_bench.py --task-id dependency-hell-2 --trials 5 \
    --model grok-4 --log-dir M2_raw_logs --network-mode offline
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TERMINAL_BENCH_DIR = REPO_ROOT / "benchmarks" / "tasks" / "terminal-bench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Terminal-Bench task with Grok-4")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--model", default="grok-4")
    parser.add_argument("--log-dir", default="M2_raw_logs")
    parser.add_argument("--network-mode", default="offline", choices=["offline", "default"])
    parser.add_argument("--terminal-bench-dir", default=str(DEFAULT_TERMINAL_BENCH_DIR))
    return parser.parse_args()


def ensure_logs_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_trial(
    task_id: str,
    model: str,
    network_mode: str,
    tb_root: Path,
    log_file: Path,
    run_id: str,
    output_root: Path,
) -> None:
    env = os.environ.copy()
    env.setdefault("XAI_API_KEY", env.get("OPENAI_API_KEY", ""))
    if not env.get("XAI_API_KEY"):
        raise RuntimeError("XAI API key missing. Set OPENAI_API_KEY or XAI_API_KEY before running.")

    # Many terminal-bench agents expect GROK_API_KEY. Mirror the value if only XAI_API_KEY is set.
    env.setdefault("GROK_API_KEY", env["XAI_API_KEY"])

    if network_mode:
        env["TB_NETWORK_MODE"] = network_mode

    # Ensure the terminal-bench source tree is importable when executing via "python -m".
    python_path = env.get("PYTHONPATH", "")
    tb_path = str(tb_root)
    env["PYTHONPATH"] = tb_path if not python_path else f"{tb_path}{os.pathsep}{python_path}"

    cmd = [
        sys.executable,
        "-m",
        "terminal_bench.cli.tb.main",
        "run",
        "--dataset-path",
        "tasks",
        "--task-id",
        task_id,
        "--agent",
        "grok-cli",
        "--model",
        model,
        "--run-id",
        run_id,
        "--output-path",
        str(output_root),
        "--n-attempts",
        "1",
        "--n-concurrent",
        "1",
    ]

    with log_file.open("w", encoding="utf-8") as fp:
        subprocess.run(cmd, cwd=str(tb_root), env=env, check=True, stdout=fp, stderr=subprocess.STDOUT)


def main() -> None:
    args = parse_args()
    tb_root = Path(args.terminal_bench_dir)
    if not tb_root.exists():
        raise FileNotFoundError(f"Terminal-Bench directory not found: {tb_root}")

    log_dir = Path(args.log_dir)
    ensure_logs_dir(log_dir)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    session_manifest = {
        "task_id": args.task_id,
        "model": args.model,
        "network_mode": args.network_mode,
        "trials": args.trials,
        "logs": [],
    }

    output_root = log_dir / f"runs_{args.task_id}_{timestamp}"
    output_root.mkdir(parents=True, exist_ok=True)

    for trial in range(1, args.trials + 1):
        log_file = log_dir / f"{args.task_id}_trial{trial}_{timestamp}.log"
        try:
            run_trial(
                args.task_id,
                args.model,
                args.network_mode,
                tb_root,
                log_file,
                run_id=f"{args.task_id}_trial{trial}_{timestamp}",
                output_root=output_root,
            )
            session_manifest["logs"].append({"trial": trial, "path": str(log_file), "status": "completed"})
        except subprocess.CalledProcessError as exc:
            session_manifest["logs"].append({"trial": trial, "path": str(log_file), "status": f"failed: {exc.returncode}"})

    manifest_path = log_dir / f"{args.task_id}_{timestamp}_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as fp:
        json.dump(session_manifest, fp, indent=2)

    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
