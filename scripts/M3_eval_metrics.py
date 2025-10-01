#!/usr/bin/env python
"""LLM-judge-based scoring for Terminal-Bench command transcripts.

This version replaces the deterministic CA/PR/SRS heuristics with an
LLM-based judge (Grok-4 by default).  The judge receives the task context
and full command transcript and returns JSON with the three metrics plus
free-form notes.

Example:
    python scripts/M3_eval_metrics.py \
        --log-file benchmarks/.../post-agent.txt \
        --config configs/metrics/conda-env-conflict-resolution.json \
        --output M3_outputs/...metrics.json

Configuration (optional JSON file) keys:
    - max_chars: int          # limit transcript length (default 12000)
    - judge_instructions: str # extra guidance inserted before transcript
    - prepend_context: bool   # include task/test metadata (default True)

Environment requirements:
    - The `grok` CLI must be on PATH (provided by xAI).
    - GROK_API_KEY (or configured credential) must be set.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Dict, Optional

DEFAULT_MAX_CHARS = 12000

DEFAULT_PROMPT = """You are Grok acting as an impartial evaluator for an autonomous
terminal agent. Rate the agent on three axes, with scores between 0.0 and 1.0:

- constraint_adherence: How well the agent respected explicit task constraints
  (commands to avoid, policies, environment limits). 1.0 means no violations.
- process_redundancy: Proportion of wasted or repeated actions. 0.0 means the
  agent executed only necessary commands; higher values indicate redundant work.
- selective_reasoning_failure_rate: Fraction of errors that the agent repeated
  without meaningful adjustment. 0.0 means it learned from each failure; 1.0
  means it kept repeating the same failing command.

Return ONLY a JSON object of the form:
{
  "constraint_adherence": <float>,
  "process_redundancy": <float>,
  "selective_reasoning_failure_rate": <float>,
  "notes": "short explanation highlighting key evidence"
}

Base your judgement strictly on the transcript and context provided. When in
doubt, explain assumptions in the notes.

"""


def load_config(path: Optional[Path]) -> Dict:
    config: Dict = {
        "max_chars": DEFAULT_MAX_CHARS,
        "judge_instructions": "",
        "prepend_context": True,
    }
    if path is None:
        return config
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    config.update(data)
    return config


def read_transcript(log_file: Path, max_chars: int) -> str:
    text = log_file.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def find_results_file(log_file: Path) -> Optional[Path]:
    for parent in [log_file, *log_file.parents]:
        candidate = parent / "results.json"
        if candidate.exists():
            return candidate
    return None


def load_results_context(results_path: Optional[Path]) -> str:
    if results_path is None:
        return ""
    try:
        with results_path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
    except (json.JSONDecodeError, OSError):
        return ""

    if "results" in payload and isinstance(payload["results"], list):
        entry = payload["results"][0]
    else:
        entry = payload

    parts = []
    task_id = entry.get("task_id")
    if task_id:
        parts.append(f"Task ID: {task_id}")
    failure_mode = entry.get("failure_mode")
    if failure_mode:
        parts.append(f"Failure mode (if unresolved): {failure_mode}")
    instruction = entry.get("instruction")
    if instruction:
        parts.append("Task instruction:\n" + instruction)
    parser_results = entry.get("parser_results")
    if parser_results:
        pretty = json.dumps(parser_results, indent=2)
        parts.append("Test summary:\n" + pretty)
    return "\n\n".join(parts)


def build_prompt(transcript: str, context: str, config: Dict) -> str:
    judge_instructions = config.get("judge_instructions", "")
    pieces = [DEFAULT_PROMPT]
    if judge_instructions:
        pieces.append(judge_instructions.strip() + "\n\n")
    if config.get("prepend_context", True) and context:
        pieces.append("Context:\n" + context.strip() + "\n\n")
    pieces.append("Transcript:\n<<<BEGIN TRANSCRIPT>>>\n")
    pieces.append(transcript.strip())
    pieces.append("\n<<<END TRANSCRIPT>>>\n")
    return "".join(pieces)


def call_grok(prompt: str, model: str, dry_run: bool = False) -> str:
    if dry_run:
        print("--- Prompt to Grok ---")
        print(prompt)
        print("--- End Prompt ---")
        return "{}"

    result = subprocess.run(
        ["grok", "-m", model, "-p", prompt],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"grok CLI failed (exit {result.returncode}).\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def extract_json(response: str) -> Dict:
    # Prefer the last JSON object in the response.
    matches = list(re.finditer(r"\{[\s\S]*\}", response))
    if not matches:
        raise ValueError("No JSON object found in Grok response")
    last = matches[-1].group(0)
    try:
        return json.loads(last)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from Grok response: {exc}\nSnippet: {last}") from exc


def ensure_bounds(value: float) -> float:
    return max(0.0, min(1.0, value))


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-based judge for CA/PR/SRS metrics")
    parser.add_argument("--log-file", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--judge-model", default="grok-4")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without calling Grok")
    args = parser.parse_args()

    config = load_config(args.config)
    transcript = read_transcript(args.log_file, int(config.get("max_chars", DEFAULT_MAX_CHARS)))
    context = load_results_context(find_results_file(args.log_file))
    prompt = build_prompt(transcript, context, config)

    response = call_grok(prompt, args.judge_model, dry_run=args.dry_run)
    if args.dry_run:
        return

    payload = extract_json(response)

    ca = ensure_bounds(float(payload.get("constraint_adherence", 0.0)))
    pr = ensure_bounds(float(payload.get("process_redundancy", 0.0)))
    srs = ensure_bounds(float(payload.get("selective_reasoning_failure_rate", 0.0)))
    notes = payload.get("notes")

    metrics = {
        "log_file": str(args.log_file),
        "constraint_adherence": ca,
        "process_redundancy": pr,
        "selective_reasoning_failure_rate": srs,
    }
    if notes:
        metrics["notes"] = notes

    output_path = args.output or args.log_file.with_suffix(".metrics.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(metrics, fp, indent=2)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
