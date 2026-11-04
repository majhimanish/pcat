"""v5 Part F: end-to-end runs inside the app repositories (spec docs/specs/v5-open-source-simulation.md).

    python scripts/v5_e2e.py run [--samples 3] [--conditions baseline,pcat] [--apps ..] [--tasks ..]
    python scripts/v5_e2e.py analyze

Each run: a fresh copy of the app at its pinned commit with the task's function removed,
committed as a baseline; `claude -p <brief request>` started in that copy with file and
shell tools (no web, no subagents), project settings only, extra CLAUDE.md directories
removed from the environment, a 10-minute limit. Condition "pcat" also serves the app's
catalog over MCP and adds the repo note to CLAUDE.md. Resumable: completed runs are
skipped. Outputs: experiments/v5/e2e/<app>/<task>/<condition>/sample_NN.{json,diff,
transcript.jsonl.gz,pcat.jsonl}.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V5 = ROOT / "experiments" / "v5"
APPS_DIR = ROOT / ".bench" / "apps"
E2E = V5 / "e2e"
# Working copies live outside this repository, under opaque names (the path must not hint at the task).
RUNS = Path(os.environ.get("PCAT_V5_RUNS", "/tmp/claude-0/-home-user-pcat/0ba369f1-7376-51dc-a4f6-4354f76fd48a/scratchpad/v5runs"))
# Paths a run must not touch: the original apps (they still contain the removed code) and this repo.
FORBIDDEN = (str(ROOT), ".bench/apps", "experiments/v5/references")
TIME_LIMIT = 600


def jobs(samples: int, conditions: list[str], apps: list[str], tasks: list[str]) -> list[dict]:
    from pcat import v5

    requests = {r["id"]: r for r in json.loads((V5 / "requests.json").read_text())["items"]}
    out = []
    for task in v5.load_tasks(V5 / "tasks.yaml"):
        if (apps and task.app not in apps) or (tasks and task.id not in tasks):
            continue
        for condition in conditions:
            for n in range(1, samples + 1):
                out.append({"task": task, "condition": condition, "sample": n,
                            "request": requests[task.id]["request"]})
    return out


def out_stem(job: dict) -> Path:
    t = job["task"]
    return E2E / t.app / t.id / job["condition"] / f"sample_{job['sample']:02d}"


def run_job(job: dict, model: str) -> dict:
    from pcat import v5

    task, condition = job["task"], job["condition"]
    stem = out_stem(job)
    stem.parent.mkdir(parents=True, exist_ok=True)
    box = RUNS / f"run-{secrets.token_hex(6)}"
    workdir = box / "repo"
    info = v5.prepare_workdir(APPS_DIR / task.app, workdir, task, condition)
    log = stem.with_suffix(".pcat.jsonl")
    log.unlink(missing_ok=True)
    mcp = None
    if condition == "pcat":
        mcp = box / "mcp.json"
        pcat = str(Path(sys.executable).parent / "pcat")
        mcp.write_text(json.dumps({"mcpServers": {"pcat": {"command": pcat, "args": [
            "serve", "--catalog", str(V5 / "catalogs" / task.app), "--log", str(log)]}}}))
    env = {k: v for k, v in os.environ.items() if k not in v5.STRIPPED_ENV}
    transcript = box / "transcript.jsonl"
    start = time.monotonic()
    with open(transcript, "w") as fh:
        proc = subprocess.Popen(v5.run_command(job["request"], model, mcp), cwd=workdir, env=env,
                                stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.PIPE, text=True)
        try:
            _, stderr = proc.communicate(timeout=TIME_LIMIT)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()
            timed_out = True
    lines = transcript.read_text().splitlines()
    summary = v5.parse_stream(lines)
    diff, files = v5.final_diff(workdir)
    with gzip.open(stem.with_suffix(".transcript.jsonl.gz"), "wt") as gz:
        gz.write("\n".join(lines) + "\n")
    stem.with_suffix(".diff").write_text(diff)
    record = {
        "app": task.app, "task": task.id, "kind": task.kind, "pattern": task.pattern,
        "relation": task.relation, "condition": condition, "sample": job["sample"],
        "request": job["request"], "model": model, "returncode": proc.returncode,
        "timed_out": timed_out, "wall_seconds": round(time.monotonic() - start, 1),
        "stderr_tail": (stderr or "")[-400:], "files_changed": files,
        "summary": {k: v for k, v in summary.items() if k != "tool_calls"},
        "tool_order": v5.tool_order(summary["tool_calls"]),
        "leaks": v5.leaks(summary["tool_calls"], workdir, FORBIDDEN),
        "pcat_calls": [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else [],
        "status": "ok" if summary["finished"] and not summary["is_error"] else (
            "timeout" if timed_out else "error"),
    }
    record["score"] = score_workdir(workdir, task, files)
    v5.write_json(stem.with_suffix(".json"), record)
    shutil.rmtree(box, ignore_errors=True)
    return record


def score_workdir(workdir: Path, task, files: list[str]) -> dict:
    """Pattern match and derivation of the new function, similarity to the original, lint."""
    from pcat import lint, provenance, v5
    from pcat.serving import CatalogService

    catalog_root = V5 / "catalogs" / task.app
    reference = (V5 / "references" / task.app / f"{task.id}.py").read_text()
    found = v5.find_new_function(workdir, task, files, reference)
    out: dict = {"new_function": None}
    if found is not None:
        node = found["node"]
        source = (workdir / found["path"]).read_text(encoding="utf-8")
        check = CatalogService(catalog_root).check_code(source)
        item = next((f for f in check["functions"] if f["line"] == node.lineno), None)
        inf = provenance.infer(node, provenance.references(catalog_root))
        info = next((i for i in provenance.functions(source) if i.node.lineno == node.lineno), None)
        out["new_function"] = {
            "path": found["path"], "function": found["function"], "how": found["how"],
            "similarity_to_original": v5.similarity_to_reference(node, reference, task.entry),
            "status": item["status"] if item else None,
            "matches_pattern": item["pattern"] if item else None,
            "marker": info.marker.ref if info and info.marker else None,
            "inferred": None if inf is None else {"pattern": inf.pattern_id, "function": inf.function,
                                                  "similarity": inf.similarity, "derived": inf.derived},
        }
    py = [str(workdir / f) for f in files if f.endswith(".py") and (workdir / f).exists()]
    empty = {"failed": False, "deviations": {"high": 0, "medium": 0, "low": 0}, "failing": 0, "findings": []}
    if not py:
        out["lint"] = empty
        return out
    baseline = subprocess.run(["git", "-C", str(workdir), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
    data = lint.lint_paths(py, catalog_root, include_inferred=True, changed_since=baseline).to_dict()
    out["lint"] = {
        "failed": data["failed"], "deviations": data["summary"]["deviations"],
        "failing": data["summary"]["failing"],
        "findings": [{"function": f["function"], "pattern": f["pattern"], "provenance": f["provenance"],
                      "codes": sorted({d["code"] for d in f["deviations"]}),
                      "high": sorted({d["code"] for d in f["deviations"] if d["severity"] == "high"})}
                     for f in data["findings"]],
    }
    return out


def cmd_run(args) -> int:
    todo, done = [], 0
    for job in jobs(args.samples, args.conditions.split(","), [a for a in args.apps.split(",") if a],
                    [t for t in args.tasks.split(",") if t]):
        path = out_stem(job).with_suffix(".json")
        if path.exists() and json.loads(path.read_text())["status"] == "ok":
            done += 1
            continue
        todo.append(job)
    print(f"running {len(todo)} end-to-end runs ({done} already done)", flush=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    total = 0.0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for n, r in enumerate(pool.map(lambda j: run_job(j, args.model), todo), 1):
            cost = r["summary"].get("cost_usd") or 0
            total += cost
            nf = r["score"]["new_function"] or {}
            print(f"[{n}/{len(todo)}] {r['app']}/{r['task']} {r['condition']} #{r['sample']:02d} "
                  f"{r['status']} ${cost:.2f} {r['wall_seconds']}s searched={r['tool_order']['searched']} "
                  f"fetched={r['tool_order']['fetched']} sim={nf.get('similarity_to_original')} "
                  f"lint_fail={r['score']['lint']['failed']} leaks={len(r['leaks'])} "
                  f"total=${total:.2f}", flush=True)
    return 0


def load_records() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(E2E.glob("*/*/*/sample_*.json"))]


def cmd_analyze(args) -> int:
    from pcat import v5

    records = load_records()
    out: dict = {"note": "v5 end-to-end; cost is the CLI's estimate and may reflect plan usage",
                 "apps": {}, "by_relation": {}, "per_task": {}}
    for app in sorted({r["app"] for r in records}):
        out["apps"][app] = {c: v5.summarize_runs([r for r in records if r["app"] == app and r["condition"] == c])
                            for c in ("baseline", "pcat")}
    out["all"] = {c: v5.summarize_runs([r for r in records if r["condition"] == c]) for c in ("baseline", "pcat")}
    for rel in ("sibling", "same"):
        out["by_relation"][rel] = {c: v5.summarize_runs([r for r in records if r.get("relation") == rel
                                                         and r["condition"] == c]) for c in ("baseline", "pcat")}
    for task in sorted({(r["app"], r["task"]) for r in records}):
        rows = [r for r in records if (r["app"], r["task"]) == task]
        out["per_task"]["/".join(task)] = {
            c: {k: v for k, v in v5.summarize_runs([r for r in rows if r["condition"] == c]).items()
                if k in ("ok", "search_rate", "fetched_right_rate", "matches_rate", "derives_rate",
                         "median_similarity_pattern_tasks", "median_similarity_negative_tasks", "lint_fail_rate",
                         "negatives_forced_a_pattern", "negatives_inferred_similar_only", "median_cost_usd")}
            for c in ("baseline", "pcat")}
    out["runs"] = [{"app": r["app"], "task": r["task"], "condition": r["condition"], "sample": r["sample"],
                    "status": r["status"], **v5.run_flags(r),
                    "new_function": (r["score"]["new_function"] or {}).get("function"),
                    "fetched": r["tool_order"]["fetched"], "lint_high": r["score"]["lint"]["findings"] and
                    sorted({c for f in r["score"]["lint"]["findings"] for c in f["high"]})}
                   for r in records]
    v5.write_json(V5 / "e2e_results.json", out)
    keys = [("search_rate", "search"), ("fetched_right_rate", "fetched right"), ("matches_rate", "matches"),
            ("derives_rate", "derives"), ("median_similarity_pattern_tasks", "sim (pattern)"),
            ("lint_fail_rate", "fails CI"), ("median_cost_usd", "median $")]
    print("| App | Condition | runs | " + " | ".join(k[1] for k in keys) + " | negatives forced / inferred-similar |")
    print("|---|---|---|" + "---|" * (len(keys) + 1))
    for app, conds in [*out["apps"].items(), ("all", out["all"])]:
        for c, s in conds.items():
            print(f"| {app} | {c} | {s['ok']}/{s['runs']} | " + " | ".join(str(s[k[0]]) for k in keys)
                  + f" | {s['negatives_forced_a_pattern']} / {s['negatives_inferred_similar_only']} of {s['negative_runs']} |")
    print(f"total cost estimate ${out['all']['baseline']['total_cost_usd'] + out['all']['pcat']['total_cost_usd']:.2f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v5 end-to-end runs")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--samples", type=int, default=3)
    r.add_argument("--conditions", default="baseline,pcat")
    r.add_argument("--apps", default="")
    r.add_argument("--tasks", default="")
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--model", default="claude-sonnet-5-5")
    sub.add_parser("analyze")
    args = parser.parse_args()
    return {"run": cmd_run, "analyze": cmd_analyze}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
