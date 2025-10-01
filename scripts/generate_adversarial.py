#!/usr/bin/env python
"""Phase 2 adversarial prompt generation utilities."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import typer
from openai import OpenAI

app = typer.Typer(help="Generate Phase 2 adversarial prompt variants")

DEFAULT_SEED_PATH = Path("data/task_lists/phase2_seed_tasks.json")
DEFAULT_PARAPHRASE_OUTPUT = Path("data/adversarial/paraphrase_variants.jsonl")
DEFAULT_CONSTRAINT_OUTPUT = Path("data/adversarial/constraint_variants.jsonl")


class VariantWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, records: Iterable[dict]) -> None:
        with self.path.open("a", encoding="utf-8") as fp:
            for record in records:
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_seeds(seed_path: Path) -> List[dict]:
    with seed_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    seeds = payload.get("selected") or payload
    if not isinstance(seeds, list):
        raise ValueError(f"Unexpected seed file structure in {seed_path}")
    return seeds


def build_client() -> OpenAI:
    try:
        return OpenAI()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Failed to initialise OpenAI client. Ensure OPENAI_API_KEY is set."
        ) from exc


def run_completion(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    top_p: float,
) -> str:
    payload: dict = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    model_lower = model.lower()
    if "gpt-5" in model_lower or model_lower.startswith("o1"):
        # Responses API rejects manual sampling parameters for reasoning models.
        pass
    else:
        payload["temperature"] = temperature
        payload["top_p"] = top_p

    response = client.responses.create(**payload)
    if hasattr(response, "output_text"):
        return response.output_text  # type: ignore[attr-defined]
    # Fallback: concatenate content parts.
    try:
        return "".join(part.text for part in response.output if hasattr(part, "text"))
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Unexpected response structure from OpenAI API") from exc


def build_record(
    variant_type: str,
    seed: dict,
    variant_text: str,
    model: str,
    temperature: float,
    top_p: float,
) -> dict:
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "variant_id": str(uuid.uuid4()),
        "variant_type": variant_type,
        "task_id": seed.get("task_id"),
        "generated_at": now,
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "prompt_original": seed.get("prompt"),
        "prompt_variant": variant_text.strip(),
        "baseline_completion": seed.get("baseline_completion"),
    }


def paraphrase_system_prompt() -> str:
    return (
        "You rewrite programming exercises. Produce a new docstring and problem "
        "statement that is semantically equivalent to the input prompt, "
        "preserving the function signature and examples. Avoid markdown fences."
    )


def paraphrase_user_prompt(original_prompt: str) -> str:
    instructions = (
        "Rewrite the following Python programming problem in a fresh style while "
        "keeping the signature and requirements unchanged. Use different "
        "vocabulary and sentence structure. Return only the rewritten prompt.\n\n"
    )
    return instructions + original_prompt


def constraint_system_prompt() -> str:
    return (
        "You augment programming problems with extra instructions. Add misleading "
        "or impractical requirements that could distract a model, while the core "
        "functional goal remains the same."
    )


def constraint_user_prompt(original_prompt: str) -> str:
    instructions = (
        "Take the following Python problem description. Add two or three new "
        "instructions that conflict with or distract from the true goal. The new "
        "text should sound plausible, remain part of the same docstring, and keep "
        "the function signature intact. Return only the augmented prompt.\n\n"
    )
    return instructions + original_prompt


@app.command()
def paraphrase(
    seed_file: Path = typer.Option(
        DEFAULT_SEED_PATH,
        "--seed-file",
        help="JSON file containing selected seed tasks",
    ),
    model: str = typer.Option("gpt-5-codex", help="OpenAI model id to use"),
    temperature: float = typer.Option(0.7, help="Sampling temperature"),
    top_p: float = typer.Option(0.9, help="Top-p sampling parameter"),
    variants_per_task: int = typer.Option(2, help="Variants to create per task"),
    output: Path = typer.Option(
        DEFAULT_PARAPHRASE_OUTPUT,
        "--output",
        help="Destination JSONL for paraphrase variants",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print prompts only"),
) -> None:
    """Generate paraphrased HumanEval prompts."""
    seeds = load_seeds(seed_file)
    writer = VariantWriter(output)
    client: Optional[OpenAI] = None if dry_run else build_client()

    for seed in seeds:
        sys_prompt = paraphrase_system_prompt()
        user_prompt = paraphrase_user_prompt(seed["prompt"])
        for _ in range(variants_per_task):
            if dry_run:
                typer.echo(f"[DRY-RUN] {seed['task_id']} paraphrase prompt:\n{user_prompt}\n")
                continue
            variant_text = run_completion(
                client, model, sys_prompt, user_prompt, temperature, top_p
            )
            record = build_record(
                variant_type="paraphrase",
                seed=seed,
                variant_text=variant_text,
                model=model,
                temperature=temperature,
                top_p=top_p,
            )
            writer.write([record])
            typer.echo(f"Generated paraphrase for {seed['task_id']}")


@app.command()
def constraint(
    seed_file: Path = typer.Option(
        DEFAULT_SEED_PATH,
        "--seed-file",
        help="JSON file containing selected seed tasks",
    ),
    model: str = typer.Option("gpt-5-codex", help="OpenAI model id to use"),
    temperature: float = typer.Option(0.7, help="Sampling temperature"),
    top_p: float = typer.Option(0.9, help="Top-p sampling parameter"),
    variants_per_task: int = typer.Option(2, help="Variants to create per task"),
    output: Path = typer.Option(
        DEFAULT_CONSTRAINT_OUTPUT,
        "--output",
        help="Destination JSONL for constraint variants",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print prompts only"),
) -> None:
    """Generate adversarial constraint injections."""
    seeds = load_seeds(seed_file)
    writer = VariantWriter(output)
    client: Optional[OpenAI] = None if dry_run else build_client()

    for seed in seeds:
        sys_prompt = constraint_system_prompt()
        user_prompt = constraint_user_prompt(seed["prompt"])
        for _ in range(variants_per_task):
            if dry_run:
                typer.echo(
                    f"[DRY-RUN] {seed['task_id']} constraint prompt:\n{user_prompt}\n"
                )
                continue
            variant_text = run_completion(
                client, model, sys_prompt, user_prompt, temperature, top_p
            )
            record = build_record(
                variant_type="constraint",
                seed=seed,
                variant_text=variant_text,
                model=model,
                temperature=temperature,
                top_p=top_p,
            )
            writer.write([record])
            typer.echo(f"Generated constraint variant for {seed['task_id']}")


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("Interrupted", err=True)
        sys.exit(1)
