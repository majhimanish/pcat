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
    previous = {}
    if target.exists():
        if args.resume:  # keep successful items; regenerate only failed ones
            for r in json.loads(target.read_text())["items"]:
                if r["request"]:
                    previous[(r["kind"], r["task"], r["need"], r["sample"])] = r
        elif not args.force:
            sys.exit(f"{target.relative_to(ROOT)} exists; it must not be regenerated "
                     "(--resume fills in failed items)")
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
    todo = [j for j in jobs if (j["kind"], j["task"], j["need"], j["sample"]) not in previous]
    print(f"generating {len(todo)} of {len(jobs)} held-out requests with claude -p ({args.model})")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        fresh = {(r["kind"], r["task"], r["need"], r["sample"]): r for r in pool.map(_heldout_job, todo)}
    records = [previous.get(k) or fresh[k] for k in
               ((j["kind"], j["task"], j["need"], j["sample"]) for j in jobs)]
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


# --------------------------------------------------------------------------- #
# End-to-end (Part E)
# --------------------------------------------------------------------------- #

E2E = OUT / "e2e"
REPO_NOTE = "This repo uses the organization's pattern catalog via the pcat tools."
PCAT_TOOLS = ("mcp__pcat__search_patterns", "mcp__pcat__get_pattern", "mcp__pcat__check_code")


def e2e_jobs(samples: int, negatives: int) -> list[dict]:
    held = json.loads((OUT / "heldout_set.json").read_text())["items"]
    suffix = variance.load_tasks(ROOT / "experiments/variance/tasks.yaml")["suffix"].strip()
    jobs = []
    for task in evaluation.cataloged_tasks(ROOT):
        requests = [r["request"] for r in held if r["kind"] == "positive" and r["task"] == task]
        for n in range(1, samples + 1):
            jobs.append({"group": task, "sample": n, "request": requests[(n - 1) % len(requests)]})
    negative_requests = [r["request"] for r in held if r["kind"] == "negative"]
    for n in range(1, negatives + 1):
        jobs.append({"group": "negative", "sample": n,
                     "request": negative_requests[(n - 1) % len(negative_requests)]})
    for job in jobs:
        job["prompt"] = f"{job['request']}\n\n{REPO_NOTE}\n\n{suffix}"
    return jobs


def _e2e_job(job: dict) -> dict:
    folder = E2E / job["group"]
    out_json = folder / f"sample_{job['sample']:02d}.json"
    log_path = folder / f"sample_{job['sample']:02d}.log.jsonl"
    log_path.unlink(missing_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="pcat-e2e-"))
    config = workdir / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"pcat": {
        "command": job["pcat"], "args": ["serve", "--catalog", str(ROOT), "--log", str(log_path)]}}}))
    generator = variance.CliGenerator(job["model"], workdir)
    generator.extra_args = ["--mcp-config", str(config), "--disable-slash-commands",
                            "--allowedTools", *PCAT_TOOLS]
    try:
        gen, attempts, error = variance.generate_with_retries(generator, job["prompt"])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    calls = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
    record = {
        **{k: job[k] for k in ("group", "sample", "request", "prompt")},
        "backend": "cli", "requested_model": job["model"], "model": gen.model if gen else None,
        "status": "ok" if gen else "failed", "error": error, "attempts": attempts,
        "raw_response": gen.text if gen else None,
        "code": variance.extract_code(gen.text) if gen else None,
        "extra": gen.extra if gen else {}, "tool_calls": calls,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    write_json(out_json, record)
    return record


def cmd_e2e(args) -> int:
    jobs = e2e_jobs(args.samples, args.negatives)
    if args.groups:
        jobs = [j for j in jobs if j["group"] in args.groups.split(",")]
    todo = []
    for job in jobs:
        path = E2E / job["group"] / f"sample_{job['sample']:02d}.json"
        if path.exists() and json.loads(path.read_text())["status"] == "ok":
            continue
        job.update(model=args.model, pcat=str(Path(sys.executable).parent / "pcat"))
        todo.append(job)
    print(f"running {len(todo)} end-to-end samples ({len(jobs) - len(todo)} already done)")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for n, r in enumerate(pool.map(_e2e_job, todo), 1):
            tools = [c["tool"] for c in r["tool_calls"]]
            print(f"[{n}/{len(todo)}] {r['group']} #{r['sample']:02d} {r['status']} tools={tools}",
                  flush=True)
    return 0


def _same_id(got: str | None, pattern_id: str) -> bool:
    return bool(got) and got.split("@")[0] == pattern_id


def score_sample(record: dict, pattern, service, pattern_shape: str | None) -> dict:
    """Metrics for one end-to-end sample (see evaluation.py for the helpers)."""
    from pcat.serving import CatalogService  # noqa: F401  (service is a CatalogService)

    calls = evaluation.tool_calls(record["tool_calls"])
    searches = calls["search_patterns"]
    gets = [c["arguments"].get("id") for c in calls["get_pattern"]]
    code = record["code"] or ""
    check = service.check_code(code)
    row = {
        "sample": record["sample"],
        "request": record["request"],
        "searched": bool(searches),
        "queries": [c["arguments"].get("request") for c in searches],
        "search_results": [c["result"].get("ids", []) for c in searches],
        "got": gets,
        "checked": bool(calls["check_code"]),
        "cost_usd": record["extra"].get("cost_usd"),
        "turns": record["extra"].get("num_turns"),
        "code_patterns": sorted({f["pattern"] for f in check.get("functions", []) if f["pattern"]}),
    }
    if pattern is None:  # negative sample
        row["used_pattern"] = bool(row["code_patterns"])
        return row
    functions = [pattern.meta.entry_point, *pattern.meta.exports]
    match = evaluation.pattern_match(check, pattern.meta.id, functions)
    similarity = None
    if pattern_shape:
        try:
            info = variance.snippet_info(code)
            similarity = round(variance.similarity(
                variance.shape.shape_text_from_canonical(info.canonical_text), pattern_shape), 3)
        except Exception:  # noqa: BLE001 - classes, syntax errors etc.: no similarity
            similarity = None
    retrieved = any(_same_id(g, pattern.meta.id) for g in gets)
    row.update(
        retrieved=retrieved,
        match_shape=match["shape"],
        match_exact=match["exact"],
        found=match["found"],
        similarity=similarity,
        library_agreement=evaluation.library_agreement(code, pattern.meta.requires),
    )
    if match["shape"]:
        row["outcome"] = "matched"
    elif not searches:
        row["outcome"] = "did_not_search"
    elif not any(pattern.meta.id in ids for ids in row["search_results"]):
        row["outcome"] = "search_missed"
    elif not gets:
        row["outcome"] = "found_but_not_fetched"
    elif not retrieved:
        row["outcome"] = "fetched_other_pattern"
    else:
        row["outcome"] = "fetched_but_changed"
    return row


def cmd_e2e_analyze(args) -> int:
    from pcat import catalog as cat
    from pcat.serving import CatalogService

    service = CatalogService(ROOT)
    tasks = evaluation.cataloged_tasks(ROOT)
    results: dict = {"note": "v3 end-to-end; prompts differ from v2.1, so baselines are indicative",
                     "tasks": {}, "negative": {}}
    total_cost = 0.0
    for group in [*tasks, "negative"]:
        records = [json.loads(p.read_text()) for p in sorted((E2E / group).glob("sample_*.json"))]
        ok = [r for r in records if r["status"] == "ok"]
        pattern = cat.get_one(ROOT, tasks[group]) if group != "negative" else None
        shape_text = None
        if pattern:
            info = variance.snippet_info(pattern.impl_path.read_text(encoding="utf-8"))
            shape_text = variance.shape.shape_text_from_canonical(info.canonical_text)
        rows = [score_sample(r, pattern, service, shape_text) for r in ok]
        total_cost += sum(r["cost_usd"] or 0 for r in rows)

        def rate(key: str) -> float:
            return round(sum(1 for r in rows if r.get(key)) / len(rows), 3) if rows else 0.0

        summary = {"samples": len(records), "ok": len(ok), "search_rate": rate("searched"),
                   "check_rate": rate("checked")}
        if pattern:
            sims = [r["similarity"] for r in rows if r["similarity"] is not None]
            summary.update(
                correct_retrieval=rate("retrieved"), pattern_match_shape=rate("match_shape"),
                pattern_match_exact=rate("match_exact"), library_agreement=rate("library_agreement"),
                median_similarity=round(sorted(sims)[len(sims) // 2], 3) if sims else None,
                outcomes={o: sum(1 for r in rows if r["outcome"] == o) for o in sorted({r["outcome"] for r in rows})},
            )
            results["tasks"][group] = {"pattern": pattern.meta.id, "summary": summary, "samples": rows}
        else:
            summary.update(fetched_pattern=round(sum(1 for r in rows if r["got"]) / len(rows), 3) if rows else 0.0,
                           code_uses_pattern=rate("used_pattern"))
            results["negative"] = {"summary": summary, "samples": rows}
    results["total_cost_usd_estimate"] = round(total_cost, 2)
    write_json(OUT / "e2e_results.json", results)
    print("| Task | Search | Correct retrieval | Pattern match (shape) | exact | Library | Check | Median sim. |")
    print("|---|---|---|---|---|---|---|---|")
    for task, data in results["tasks"].items():
        s = data["summary"]
        print(f"| {task} | {s['search_rate']:.2f} | {s['correct_retrieval']:.2f} | {s['pattern_match_shape']:.2f} "
              f"| {s['pattern_match_exact']:.2f} | {s['library_agreement']:.2f} | {s['check_rate']:.2f} "
              f"| {s['median_similarity']} |")
    n = results["negative"]["summary"]
    print(f"negatives: searched {n['search_rate']:.2f}, fetched a pattern {n['fetched_pattern']:.2f}, "
          f"code contains a pattern {n['code_uses_pattern']:.2f}; cost estimate ${results['total_cost_usd_estimate']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v3 evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    h = sub.add_parser("heldout")
    h.add_argument("--per-task", type=int, default=5)
    h.add_argument("--model", default=variance.DEFAULT_MODEL)
    h.add_argument("--jobs", type=int, default=8)
    h.add_argument("--force", action="store_true")
    h.add_argument("--resume", action="store_true", help="regenerate only failed items")
    r = sub.add_parser("retrieval")
    r.add_argument("--out", default=None, help="file name under experiments/mcp/")
    e = sub.add_parser("e2e")
    e.add_argument("--samples", type=int, default=20, help="per cataloged task")
    e.add_argument("--negatives", type=int, default=20)
    e.add_argument("--groups", default="", help="comma-separated tasks and/or 'negative'")
    e.add_argument("--model", default=variance.DEFAULT_MODEL)
    e.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    sub.add_parser("e2e-analyze")
    return {"heldout": cmd_heldout, "retrieval": cmd_retrieval, "e2e": cmd_e2e,
            "e2e-analyze": cmd_e2e_analyze}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
