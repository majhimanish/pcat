"""v3 evaluation driver (spec docs/specs/v3-mcp-server.md, Parts D and E).

    python scripts/mcp_eval.py heldout            # generate the held-out request set (claude -p)
    python scripts/mcp_eval.py retrieval          # calibrate on dev, evaluate dev + held-out
    python scripts/mcp_eval.py e2e [--samples N]  # end-to-end samples with the MCP server
    python scripts/mcp_eval.py e2e-analyze        # metrics from the end-to-end samples

Outputs go to experiments/mcp/. Logic lives in src/pcat/evaluation.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pcat import evaluation, search, variance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "mcp"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def fresh_cli(model: str):
    workdir = Path(tempfile.mkdtemp(prefix="pcat-mcp-eval-"))
    return variance.CliGenerator(model, workdir), workdir


# --------------------------------------------------------------------------- #
# Held-out set
# --------------------------------------------------------------------------- #


def _heldout_job(job: dict) -> dict:
    generator, workdir = fresh_cli(job["model"])
    try:
        gen, attempts, error = variance.generate_with_retries(generator, job["prompt"])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return {
        **{k: job[k] for k in ("kind", "task", "need", "sample", "prompt")},
        "request": evaluation.clean_request(gen.text) if gen else None,
        "raw_response": gen.text if gen else None,
        "model": gen.model if gen else None,
        "backend": "cli",
        "attempts": attempts,
        "error": error,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def cmd_heldout(args) -> int:
    target = OUT / "heldout_set.json"
    if target.exists() and not args.force:
        sys.exit(f"{target.relative_to(ROOT)} exists; it must not be regenerated (use --force)")
    needs = json.loads((OUT / "heldout_needs.json").read_text())
    jobs = []
    for task, need in needs["positives"].items():
        for n in range(1, args.per_task + 1):
            jobs.append({"kind": "positive", "task": task, "need": need, "sample": n})
    for n, need in enumerate(needs["negatives"], 1):
        jobs.append({"kind": "negative", "task": None, "need": need, "sample": n})
    for job in jobs:
        job["prompt"] = evaluation.HELDOUT_PROMPT.format(need=job["need"])
        job["model"] = args.model
    print(f"generating {len(jobs)} held-out requests with claude -p ({args.model})")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        records = list(pool.map(_heldout_job, jobs))
    failed = [r for r in records if not r["request"]]
    write_json(target, {"model": args.model, "prompt_template": evaluation.HELDOUT_PROMPT,
                        "items": records})
    print(f"wrote {target.relative_to(ROOT)}: {len(records) - len(failed)} ok, {len(failed)} failed")
    for r in records[:3] + records[-2:]:
        print(f"  [{r['kind']}:{r['task']}] {r['request']}")
    return 0


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #


def ranked_items(items: list[dict], index: search.SearchIndex) -> list[dict]:
    out = []
    for item in items:
        ranked = [(h.id, h.score) for h in index.rank(item["request"])]
        out.append({**item, "ranked": ranked[:5]})
    return out


def heldout_items() -> list[dict]:
    data = json.loads((OUT / "heldout_set.json").read_text())
    patterns = evaluation.cataloged_tasks(ROOT)
    return [
        {"task": r["task"], "request": r["request"],
         "expected": patterns[r["task"]] if r["kind"] == "positive" else None}
        for r in data["items"] if r["request"]
    ]


def cmd_retrieval(args) -> int:
    index = search.SearchIndex.from_root(ROOT)
    dev = ranked_items(evaluation.dev_set(ROOT), index)
    threshold, table = evaluation.calibrate_threshold(dev)
    results = {
        "search_constants": {"MATCH_THRESHOLD": search.MATCH_THRESHOLD,
                             "BM25_K1": search.BM25_K1, "BM25_B": search.BM25_B},
        "calibration": {"set": "development", "chosen_threshold": threshold, "candidates": table},
        "development": evaluation.retrieval_metrics(dev, search.MATCH_THRESHOLD),
        "development_items": dev,
    }
    if (OUT / "heldout_set.json").exists():
        held = ranked_items(heldout_items(), index)
        results["heldout"] = evaluation.retrieval_metrics(held, search.MATCH_THRESHOLD)
        results["heldout_items"] = held
    name = args.out or "retrieval.json"
    write_json(OUT / name, results)
    print(f"calibrated threshold on dev: {threshold} (search.MATCH_THRESHOLD = {search.MATCH_THRESHOLD})")
    for key in ("development", "heldout"):
        if key in results:
            r = results[key]
            print(f"{key:12} top1 {r['top1']:.3f}  top3 {r['top3']:.3f}  "
                  f"false-match {r['false_match_rate']:.3f}  (ranking only top1 "
                  f"{r['top1_ignoring_threshold']:.3f}; {r['positives']} pos, {r['negatives']} neg)")
    print(f"wrote experiments/mcp/{name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v3 evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    h = sub.add_parser("heldout")
    h.add_argument("--per-task", type=int, default=5)
    h.add_argument("--model", default=variance.DEFAULT_MODEL)
    h.add_argument("--jobs", type=int, default=8)
    h.add_argument("--force", action="store_true")
    r = sub.add_parser("retrieval")
    r.add_argument("--out", default=None, help="file name under experiments/mcp/")
    args = parser.parse_args()
    return {"heldout": cmd_heldout, "retrieval": cmd_retrieval}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
