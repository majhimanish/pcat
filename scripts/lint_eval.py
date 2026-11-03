"""v4 evaluation driver (spec docs/specs/v4-linter.md).

    python scripts/lint_eval.py calibrate        # inference threshold (Part A), existing data only

Outputs go to experiments/linter/. Logic lives in src/pcat/linteval.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pcat import evaluation, linteval, provenance
from pcat.serving import CatalogService

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "linter"
V3 = ROOT / "experiments" / "mcp" / "e2e"
V21 = ROOT / "experiments" / "variance" / "runs" / "main"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _records(group: str) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((V3 / group).glob("sample_*.json"))]


def calibration_items(root: Path = ROOT) -> list[dict]:
    """Labeled functions: derived (v3 positives) and not derived (v2.1 FastAPI A/B, v3 negatives)."""
    refs = provenance.references(root)
    tasks = evaluation.cataloged_tasks(root)
    service = CatalogService(root)
    items = []
    for task, pattern_id in tasks.items():
        own = [r for r in refs if r.pattern_id == pattern_id]
        for rec in _records(task):
            if rec["status"] != "ok" or not rec["code"]:
                continue
            labels = dict(linteval.derived_functions(rec["code"], own))
            for qualname, _, text in linteval.sample_functions(rec["code"]):
                if qualname in labels:
                    item = linteval.ranked_item(text, refs, labels[qualname])
                    item.update(source=f"v3/{task}/{rec['sample']:02d}", function=qualname)
                    items.append(item)
    negatives = [(f"v2.1/fastapi_create_user/{c}/{p.stem}", p.read_text())
                 for c in ("A", "B") for p in sorted((V21 / "fastapi_create_user" / c).glob("sample_*.py"))]
    negatives += [(f"v3/negative/{r['sample']:02d}", r["code"]) for r in _records("negative")
                  if r["status"] == "ok" and r["code"]]
    for source, code in negatives:
        try:
            matched = {f["name"] for f in service.check_code(code).get("functions", []) if f["pattern"]}
        except Exception:  # noqa: BLE001
            matched = set()
        for qualname, _, text in linteval.sample_functions(code):
            if qualname in matched:  # really derived (a pattern used as a sub-task): not a negative
                continue
            item = linteval.ranked_item(text, refs, None)
            item.update(source=source, function=qualname)
            items.append(item)
    return items


def cmd_calibrate(args) -> int:
    items = calibration_items()
    threshold, table = evaluation.calibrate_threshold(items)
    summary = linteval.inference_summary(items, threshold)
    write_json(OUT / "inference_calibration.json", {
        "chosen_threshold": threshold,
        "constant": provenance.INFERENCE_THRESHOLD,
        "summary": summary,
        "candidates": table,
        "items": items,
    })
    print(json.dumps(summary, indent=2))
    print(f"calibrated threshold: {threshold} (provenance.INFERENCE_THRESHOLD = {provenance.INFERENCE_THRESHOLD})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v4 evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("calibrate")
    args = parser.parse_args()
    return {"calibrate": cmd_calibrate}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
