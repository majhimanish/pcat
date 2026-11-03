"""How many v2.1 variance samples already matched the v2.2 catalog patterns.

    python scripts/catalog_coverage.py [--condition B] [--run-id main]

For each task with a catalog pattern (docs/catalog-review/choices.yaml), compares
the run's valid samples with the pattern's impl.py at two levels:
- whole snippet: the v2.1 snippet normalization (pcat.variance), shape and exact
- entry function: any function in the sample vs the pattern's entry point alone
  (canonicalized like the miner does), shape and exact
- closest sample: highest similarity of a sample's shape text to the pattern's
  (difflib ratio, as in the v2.1 near-shape metric; 1.00 = same shape)
Read-only: experiments/ is not modified. Prints a Markdown table.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import yaml

from pcat import catalog as cat
from pcat import miner, variance

ROOT = Path(__file__).resolve().parents[1]


def entry_fingerprints(pattern) -> tuple[str, str]:
    tree = ast.parse(pattern.impl_path.read_text(encoding="utf-8"))
    entry = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == pattern.meta.entry_point)
    mined = miner.mine_function(entry)
    return mined["exact_fingerprint"], mined["shape_fingerprint"]


def sample_function_fingerprints(code: str) -> tuple[set[str], set[str]]:
    exact, shapes = set(), set()
    for f in miner.analyze_source(code.encode(), miner.MineSettings(fragments=False))["functions"]:
        if f["error"] is None:
            exact.add(f["exact_fingerprint"])
            shapes.add(f["shape_fingerprint"])
    return exact, shapes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--condition", default="B")
    parser.add_argument("--run-id", default="main")
    args = parser.parse_args()
    choices = yaml.safe_load((ROOT / "docs/catalog-review/choices.yaml").read_text())["choices"]
    run = ROOT / "experiments/variance/runs" / args.run_id
    print("| Task | Pattern | Valid samples | Whole snippet: same shape | same exact "
          "| Entry function: same shape | same exact | Closest sample (similarity) |")
    print("|---|---|---|---|---|---|---|---|")
    for task, choice in choices.items():
        if choice["variant"] == "defer":
            print(f"| {task} | (deferred) | | | | | | |")
            continue
        pattern = cat.get_one(ROOT, choice["pattern_id"])
        snippet = variance.snippet_info(pattern.impl_path.read_text(encoding="utf-8"))
        entry_exact, entry_shape = entry_fingerprints(pattern)
        valid = whole_shape = whole_exact = fn_shape = fn_exact = 0
        pattern_shape_text = variance.shape.shape_text_from_canonical(snippet.canonical_text)
        closest = 0.0
        for record in variance.load_samples(run, task, args.condition):
            row = variance.analyze_sample(record)
            if "invalid_reason" in row:
                continue
            valid += 1
            whole_shape += row["shape_fingerprint"] == snippet.shape_fingerprint
            whole_exact += row["exact_fingerprint"] == snippet.exact_fingerprint
            closest = max(closest, variance.similarity(row["shape_text"], pattern_shape_text))
            exact, shapes = sample_function_fingerprints(record["code"])
            fn_shape += entry_shape in shapes
            fn_exact += entry_exact in exact
        print(f"| {task} | `{choice['pattern_id']}` | {valid} | {whole_shape} | {whole_exact} "
              f"| {fn_shape} | {fn_exact} | {closest:.2f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
