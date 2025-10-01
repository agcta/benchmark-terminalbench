#!/usr/bin/env python
"""Extract failure metadata from lm-evaluation-harness samples for triage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_CONFIG = Path("configs/models/openai_gpt5_baseline.yaml")


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def collect_failures(run_dir: Path, task: str) -> Dict[str, Any]:
    candidates = [
        run_dir / "samples" / f"{task}.jsonl",
        run_dir / f"samples_{task}.jsonl",
    ]
    samples_path = None
    for candidate in candidates:
        if candidate.exists():
            samples_path = candidate
            break

    failures = []

    if samples_path is None:
        raise FileNotFoundError(
            f"Samples file not found in {[str(c) for c in candidates]}"
        )

    with samples_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            payload = json.loads(line)
            if "pass@1" in payload:
                passed = bool(payload.get("pass@1"))
            else:
                evals = payload.get("eval") or {}
                passed = evals.get("passed", False)
            if passed:
                continue
            doc = payload.get("doc", {})
            resps = payload.get("resps", [])
            completion = None
            if resps and resps[0]:
                completion = resps[0][0]
            failure = {
                "task_id": doc.get("task_id") or payload.get("task_id"),
                "prompt": doc.get("prompt") or payload.get("prompt"),
                "completion": completion or payload.get("decoded_completion"),
                "stderr": payload.get("stderr"),
                "exit_code": payload.get("exit_code") or (
                    payload.get("eval", {}) or {}
                ).get("exit_code"),
                "failure_type": (
                    payload.get("failure_type")
                    or (payload.get("eval") or {}).get("failure_type")
                ),
                "pass@1": payload.get("pass@1"),
            }
            failures.append(failure)
    return {"task": task, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect failure cases from a baseline run")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Config used for the run")
    parser.add_argument("--run-dir", type=Path, help="Override run directory (defaults to config)")
    parser.add_argument("--output", type=Path, help="Optional output JSON file")
    args = parser.parse_args()

    config = load_config(args.config)
    eval_cfg = config["eval"]
    run_dir = args.run_dir or Path(eval_cfg.get("artifacts_dir", "artifacts")) / eval_cfg.get("run_id", "baseline")

    task = eval_cfg.get("task", "humaneval")
    summary = collect_failures(run_dir, task)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as fp:
            json.dump(summary, fp, indent=2)
        print(f"[INFO] Failure summary written to {args.output}")
    else:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
