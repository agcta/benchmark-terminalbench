#!/usr/bin/env python
"""Aggregate baseline vs. adversarial HumanEval metrics for Phase 3."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import typer

app = typer.Typer(help="Summarise HumanEval robustness metrics across runs")

DEFAULT_RUNS = {
    "baseline": Path("artifacts/baseline/baseline_humaneval_plus/results.json"),
    "paraphrase": Path("artifacts/paraphrase/humaneval_paraphrase/results.json"),
    "constraint": Path("artifacts/constraint/humaneval_constraint/results.json"),
}


def extract_pass_at_1(payload: Dict) -> float:
    task = next(iter(payload.get("results", {})), None)
    if task is None:
        raise KeyError("No task entries found in results.json")
    metrics = payload["results"][task]
    if "pass@1" in metrics:
        return float(metrics["pass@1"])
    for key, value in metrics.items():
        if key.startswith("pass@1"):
            return float(value)
    raise KeyError("pass@1 metric not found in results.json")


@app.command()
def main(
    baseline: Path = typer.Option(
        DEFAULT_RUNS["baseline"], "--baseline", help="Baseline results.json"
    ),
    paraphrase: Path = typer.Option(
        DEFAULT_RUNS["paraphrase"], "--paraphrase", help="Paraphrase results.json"
    ),
    constraint: Path = typer.Option(
        DEFAULT_RUNS["constraint"], "--constraint", help="Constraint results.json"
    ),
    output: Path = typer.Option(
        Path("artifacts/metrics/phase3_summary.json"),
        "--output",
        help="Where to write aggregated metrics",
    ),
) -> None:
    runs = {
        "baseline": baseline,
        "paraphrase": paraphrase,
        "constraint": constraint,
    }

    summary = {}
    for name, path in runs.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing results file: {path}")
        payload = json.loads(path.read_text())
        pass_at_1 = extract_pass_at_1(payload)
        summary[name] = {
            "pass_at_1": pass_at_1,
            "source": str(path),
        }

    baseline_value = summary["baseline"]["pass_at_1"]
    for name in ("paraphrase", "constraint"):
        delta = summary[name]["pass_at_1"] - baseline_value
        summary[name]["delta_vs_baseline"] = delta

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2))

    typer.echo("Phase 3 summary:")
    typer.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
