#!/usr/bin/env python
"""Compile adversarial prompt variants into HumanEval-compatible JSONL datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

from datasets import load_dataset

VARIANT_FILES = {
    "paraphrase": Path("data/adversarial/paraphrase_variants.jsonl"),
    "constraint": Path("data/adversarial/constraint_variants.jsonl"),
}

OUTPUT_FILES = {
    "paraphrase": Path("data/adversarial/humaneval_paraphrase.jsonl"),
    "constraint": Path("data/adversarial/humaneval_constraint.jsonl"),
}


def read_variants(path: Path) -> Iterable[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Variant file not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            yield json.loads(line)


def main() -> None:
    base_dataset = load_dataset("openai/openai_humaneval", split="test")
    task_lookup = {
        item["task_id"]: {
            "canonical_solution": item["canonical_solution"],
            "test": item["test"],
            "entry_point": item["entry_point"],
        }
        for item in base_dataset
    }

    for name, variant_path in VARIANT_FILES.items():
        variants = list(read_variants(variant_path))
        output_path = OUTPUT_FILES[name]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rows = []
        for variant in variants:
            task_id = variant.get("task_id")
            if not task_id or task_id not in task_lookup:
                continue
            base = task_lookup[task_id]
            rows.append(
                {
                    "task_id": task_id,
                    "prompt": variant.get("prompt_variant", variant.get("prompt_original")),
                    "canonical_solution": base["canonical_solution"],
                    "test": base["test"],
                    "entry_point": base["entry_point"],
                    "variant_id": variant.get("variant_id"),
                    "variant_type": variant.get("variant_type"),
                }
            )

        with output_path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")

        print(f"Wrote {len(rows)} records to {output_path}")


if __name__ == "__main__":
    main()
