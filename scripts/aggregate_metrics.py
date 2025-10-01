#!/usr/bin/env python
"""Aggregate per-trial diagnostics into a single JSON summary.

Usage:
    python scripts/aggregate_metrics.py \
        --metrics-dir M3_outputs \
        --output reports/M3_Grok4_Diagnosis.json

Optional flags:
    --task-id <id>      # filter to a specific Terminal-Bench task
    --include-raw       # emit raw trial entries only (skip computed stats)

The script pairs each metrics JSON produced by M3_eval_metrics.py with the
corresponding Terminal-Bench results.json and manifests a consolidated view
containing:
    * task_id, trial_id, timestamp
    * model + network mode (when available)
    * pass/fail outcome and failure mode
    * CA / PR / SRS metrics
    * resolved/unresolved counts

Aggregate statistics (mean CA/PR/SRS, pass@k) are computed per task and for the
filtered set as a whole. The output is a JSON dictionary with two keys:
    "trials": [...]  # list of per-trial records
    "summary": {...} # aggregate statistics
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional


@dataclass
class TrialRecord:
    task_id: str
    trial_id: str
    timestamp: Optional[str]
    model: Optional[str]
    network_mode: Optional[str]
    manifest_path: Optional[str]
    metrics_path: Path
    results_path: Optional[Path]
    constraint_adherence: float
    process_redundancy: float
    selective_reasoning_failure_rate: float
    resolved: bool
    failure_mode: Optional[str]
    notes: Optional[str] = None


def find_results_file(log_path: Path) -> Optional[Path]:
    """Walk up from the log file until a sibling results.json is found."""

    for parent in [log_path, *log_path.parents]:
        candidate = parent / "results.json"
        if candidate.exists():
            return candidate
    return None


def extract_trial_metadata(results_path: Path) -> Dict:
    with results_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    # Two possible layouts:
    #   1. Aggregate: {"results": [{...}], "n_resolved": int, ...}
    #   2. Per-trial: {"trial_name": ..., "task_id": ..., ...}
    if "results" in payload and isinstance(payload["results"], list):
        entry = payload["results"][0]
        resolved_count = payload.get("n_resolved", 0)
        unresolved_count = payload.get("n_unresolved", 0)
    else:
        entry = payload
        resolved_count = 1 if entry.get("is_resolved") else 0
        unresolved_count = 0 if entry.get("is_resolved") else 1

    trial_meta = {
        "task_id": entry.get("task_id"),
        "trial_name": entry.get("trial_name"),
        "failure_mode": entry.get("failure_mode"),
        "is_resolved": bool(entry.get("is_resolved")),
        "trial_started_at": entry.get("trial_started_at"),
        "model": entry.get("model"),
        "network_mode": entry.get("network_mode"),
    }

    return {
        "trial_meta": trial_meta,
        "n_resolved": resolved_count,
        "n_unresolved": unresolved_count,
    }


def build_trial_record(metrics_path: Path) -> Optional[TrialRecord]:
    with metrics_path.open("r", encoding="utf-8") as fp:
        metrics = json.load(fp)

    if isinstance(metrics, list):
        # Legacy aggregated payload; skip and let caller aggregate individual files.
        return None

    log_file = metrics.get("log_file")
    if not log_file:
        return None

    log_path = Path(log_file)
    results_path = find_results_file(log_path)

    trial_id = (
        results_path.parent.name
        if results_path is not None
        else (log_path.parent.name or metrics_path.stem)
    )

    model = network_mode = timestamp = manifest_path = None
    task_id = None
    resolved = False
    failure_mode = None

    if results_path and results_path.exists():
        try:
            meta = extract_trial_metadata(results_path)
            trial_meta = meta["trial_meta"]
            task_id = trial_meta.get("task_id")
            failure_mode = trial_meta.get("failure_mode")
            resolved = trial_meta.get("is_resolved", False)
            timestamp = trial_meta.get("trial_started_at")
            model = trial_meta.get("model")
            network_mode = trial_meta.get("network_mode")
        except ValueError:
            pass

    notes = metrics.get("notes")

    return TrialRecord(
        task_id=task_id or "unknown",
        trial_id=trial_id,
        timestamp=timestamp,
        model=model,
        network_mode=network_mode,
        manifest_path=manifest_path,
        metrics_path=metrics_path,
        results_path=results_path,
        constraint_adherence=metrics.get("constraint_adherence", 0.0),
        process_redundancy=metrics.get("process_redundancy", 0.0),
        selective_reasoning_failure_rate=metrics.get("selective_reasoning_failure_rate", 0.0),
        resolved=resolved,
        failure_mode=failure_mode,
        notes=notes,
    )


def summarise(trials: List[TrialRecord]) -> Dict:
    if not trials:
        return {
            "count": 0,
            "pass_at_1": 0.0,
            "ca_mean": 0.0,
            "pr_mean": 0.0,
            "srs_mean": 0.0,
        }

    pass_rate = sum(1 for t in trials if t.resolved) / len(trials)

    return {
        "count": len(trials),
        "pass_at_1": pass_rate,
        "ca_mean": mean(t.constraint_adherence for t in trials),
        "pr_mean": mean(t.process_redundancy for t in trials),
        "srs_mean": mean(t.selective_reasoning_failure_rate for t in trials),
    }


def render(trials: List[TrialRecord]) -> List[Dict]:
    rendered = []
    for record in trials:
        rendered.append(
            {
                "task_id": record.task_id,
                "trial_id": record.trial_id,
                "timestamp": record.timestamp,
                "model": record.model,
                "network_mode": record.network_mode,
                "metrics_path": str(record.metrics_path),
                "results_path": str(record.results_path) if record.results_path else None,
                "constraint_adherence": record.constraint_adherence,
                "process_redundancy": record.process_redundancy,
                "selective_reasoning_failure_rate": record.selective_reasoning_failure_rate,
                "resolved": record.resolved,
                "failure_mode": record.failure_mode,
                "notes": record.notes,
            }
        )
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate M3 metric outputs into a summary JSON")
    parser.add_argument("--metrics-dir", default="M3_outputs")
    parser.add_argument("--output", default="reports/M3_Grok4_Diagnosis.json")
    parser.add_argument("--task-id", help="Filter to a specific Terminal-Bench task")
    parser.add_argument("--include-raw", action="store_true", help="Only emit per-trial entries (no summary)")
    args = parser.parse_args()

    metrics_dir = Path(args.metrics_dir)
    if not metrics_dir.exists():
        raise FileNotFoundError(f"Metrics directory not found: {metrics_dir}")

    records: List[TrialRecord] = []
    for metrics_path in sorted(metrics_dir.glob("*.json")):
        record = build_trial_record(metrics_path)
        if record is None:
            continue
        if args.task_id and record.task_id != args.task_id:
            continue
        records.append(record)

    by_task: Dict[str, List[TrialRecord]] = defaultdict(list)
    for record in records:
        by_task[record.task_id].append(record)

    payload = {
        "trials": render(records),
        "summary": {}
    }

    if not args.include_raw:
        payload["summary"]["overall"] = summarise(records)
        payload["summary"]["per_task"] = {
            task_id: summarise(entries)
            for task_id, entries in by_task.items()
        }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)

    print(f"Wrote aggregate metrics to {output_path}")


if __name__ == "__main__":
    main()
