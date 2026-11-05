"""v5.2: catalog versus an unsafe neighbour (spec docs/specs/v5.2-unsafe-neighbour.md).

    python scripts/v5_2.py prepare      # references + file skeletons from .bench/apps (commit them)
    python scripts/v5_2.py verify       # every neighbour violates its guards, every original passes
    python scripts/v5_2.py requests     # brief requests via fresh `claude -p` processes (commit them)
    python scripts/v5_2.py run [--samples 3] [--conditions baseline,pcat] [--apps ..] [--tasks ..]
    python scripts/v5_2.py analyze      # Part D scoring -> experiments/v5.2/results.json

Working copies are made exactly as in v5 (scripts/v5_e2e.py), plus the planted neighbour,
before the baseline commit. Outputs: experiments/v5.2/e2e/<app>/<task>/<condition>/sample_NN.*
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V52 = ROOT / "experiments" / "v5.2"
V5 = ROOT / "experiments" / "v5"
APPS_DIR = ROOT / ".bench" / "apps"


def tasks():
    from pcat import v52

    return v52.load_tasks(V52 / "tasks.yaml")


def catalog_pattern(app: str, pattern_id: str):
    from pcat import catalog as cat

    return cat.get_one(V5 / "catalogs" / app, pattern_id)


def cmd_prepare(args) -> int:
    from pcat import v5, v52

    for t in tasks():
        source = (APPS_DIR / t.app / t.file).read_text(encoding="utf-8")
        reference = v5.reference_source(source, t.remove)
        without, _ = v5.remove_functions(source, t.remove)
        code = v52.neighbour_code(ROOT, t)
        context = v52.context_for(without, [reference, code])
        for kind, text in (("references", reference), ("context", context)):
            path = V52 / kind / t.app / f"{t.id}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        print(f"{t.app}/{t.id}: {len(reference.splitlines())} reference lines, "
              f"{len(context.splitlines())} context lines")
    return 0


def check_task(t, source_without: str, code: str, reference: str) -> dict:
    """Guards on the planted neighbour and on each removed original, in `source_without`."""
    from pcat import v52

    pattern = catalog_pattern(t.app, t.pattern)
    module = v52.module_from_rel(t.file)
    planted = v52.plant(source_without, code, t.neighbour.anchor)
    res = v52.guard_results(planted, t.neighbour.function, pattern, t.neighbour.pattern_function, module)
    out = {"neighbour": {"violated": sorted(v52.violated(res)), "skipped": sorted(v52.skipped(res)),
                         "intended": list(t.neighbour.violates)}, "originals": {}}
    restored = source_without.rstrip("\n") + "\n\n\n" + reference
    for fn, pfn in t.targets:
        r = v52.guard_results(restored, fn, pattern, pfn, module)
        out["originals"][fn] = {"pattern_function": pfn, "checked": len(r),
                                "violated": sorted(v52.violated(r)), "skipped": sorted(v52.skipped(r))}
    return out


def cmd_verify(args) -> int:
    from pcat import v5, v52

    bad = 0
    report = {}
    for t in tasks():
        code = v52.neighbour_code(ROOT, t)
        reference = (V52 / "references" / t.app / f"{t.id}.py").read_text(encoding="utf-8")
        context = (V52 / "context" / t.app / f"{t.id}.py").read_text(encoding="utf-8")
        results = {"context": check_task(t, context, code, reference)}
        real = APPS_DIR / t.app / t.file
        if real.exists():
            without, _ = v5.remove_functions(real.read_text(encoding="utf-8"), t.remove)
            results["real_file"] = check_task(t, without, code, reference)
        for where, r in results.items():
            missing = set(r["neighbour"]["intended"]) - set(r["neighbour"]["violated"])
            failing = {fn: o["violated"] for fn, o in r["originals"].items() if o["violated"] or o["skipped"]}
            ok = not missing and not failing and not r["neighbour"]["skipped"]
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {t.app}/{t.id} [{where}]: neighbour violates "
                  f"{r['neighbour']['violated']}" + (f"; MISSING {sorted(missing)}" if missing else "")
                  + (f"; originals failing {failing}" if failing else ""))
        report[t.id] = results
    if args.write:
        v5.write_json(V52 / "verify.json", report)
    return 1 if bad else 0


# --------------------------------------------------------------------------- #
# Part C: runs (the v5 harness, plus the planted neighbour)
# --------------------------------------------------------------------------- #

E2E = V52 / "e2e"
RUNS = Path(os.environ.get("PCAT_V52_RUNS", "/tmp/claude-0/-home-user-pcat/0ba369f1-7376-51dc-a4f6-4354f76fd48a/scratchpad/v52runs"))
# Paths a run must not touch: the original apps, this repo (references, neighbours, manifests).
FORBIDDEN = (str(ROOT), ".bench/apps", "experiments/v5/references", "experiments/v5.2")
TIME_LIMIT = 600


def jobs(samples: int, conditions: list[str], apps: list[str], task_ids: list[str]) -> list[dict]:
    requests = {r["id"]: r["request"] for r in json.loads((V52 / "requests.json").read_text())["items"]}
    out = []
    for t in tasks():
        if (apps and t.app not in apps) or (task_ids and t.id not in task_ids):
            continue
        for condition in conditions:
            for n in range(1, samples + 1):
                out.append({"task": t, "condition": condition, "sample": n, "request": requests[t.id]})
    return out


def out_stem(job: dict) -> Path:
    t = job["task"]
    return E2E / t.app / t.id / job["condition"] / f"sample_{job['sample']:02d}"


def run_job(job: dict, model: str) -> dict:
    import gzip
    import secrets
    import shutil
    import subprocess
    import time

    from pcat import v5, v52

    task, condition = job["task"], job["condition"]
    stem = out_stem(job)
    stem.parent.mkdir(parents=True, exist_ok=True)
    box = RUNS / f"run-{secrets.token_hex(6)}"
    workdir = box / "repo"
    info = v52.prepare_workdir(APPS_DIR / task.app, workdir, task, condition, v52.neighbour_code(ROOT, task))
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
        "app": task.app, "task": task.id, "pattern": task.pattern, "relation": task.relation,
        "condition": condition, "sample": job["sample"], "request": job["request"], "model": model,
        "returncode": proc.returncode, "timed_out": timed_out, "wall_seconds": round(time.monotonic() - start, 1),
        "stderr_tail": (stderr or "")[-400:], "files_changed": files, "baseline": info["baseline"],
        "summary": {k: v for k, v in summary.items() if k != "tool_calls"},
        "tool_calls": summary["tool_calls"],
        "tool_order": v5.tool_order(summary["tool_calls"]),
        "leaks": v5.leaks(summary["tool_calls"], workdir, FORBIDDEN),
        "pcat_calls": [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else [],
        "status": "ok" if summary["finished"] and not summary["is_error"] else (
            "timeout" if timed_out else "error"),
    }
    v5.write_json(stem.with_suffix(".json"), record)
    shutil.rmtree(box, ignore_errors=True)
    return record


def cmd_run(args) -> int:
    from concurrent.futures import ThreadPoolExecutor

    todo, done, spent = [], 0, 0.0
    for job in jobs(args.samples, args.conditions.split(","), [a for a in args.apps.split(",") if a],
                    [t for t in args.tasks.split(",") if t]):
        path = out_stem(job).with_suffix(".json")
        if path.exists():
            rec = json.loads(path.read_text())
            if rec["status"] == "ok":
                done += 1
                spent += rec["summary"].get("cost_usd") or 0
                continue
        todo.append(job)
    print(f"running {len(todo)} runs ({done} already done, ${spent:.2f} so far)", flush=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    total = spent
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for n, r in enumerate(pool.map(lambda j: run_job(j, args.model), todo), 1):
            cost = r["summary"].get("cost_usd") or 0
            total += cost
            print(f"[{n}/{len(todo)}] {r['app']}/{r['task']} {r['condition']} #{r['sample']:02d} {r['status']} "
                  f"${cost:.2f} {r['wall_seconds']}s searched={r['tool_order']['searched']} "
                  f"fetched={r['tool_order']['fetched']} files={r['files_changed']} leaks={len(r['leaks'])} "
                  f"total=${total:.2f}", flush=True)
            if total > args.cap:
                print(f"cost cap ${args.cap} reached; stopping (rerun to resume)", flush=True)
                os._exit(3)
    return 0


REQUEST_ATTEMPTS = 3  # fresh processes per task when a request mentions security or the neighbour


def cmd_requests(args) -> int:
    import datetime as dt
    import shutil
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    from pcat import evaluation, v5, v52, variance

    target = V52 / "requests.json"
    previous = {}
    if target.exists():
        if not args.resume:
            sys.exit("experiments/v5.2/requests.json exists; it must not be regenerated (--resume fills gaps)")
        previous = {r["id"]: r for r in json.loads(target.read_text())["items"] if r["request"]}
    todo = [t for t in tasks() if t.id not in previous]

    def one(prompt):
        workdir = Path(tempfile.mkdtemp(prefix="pcat-v52-req-"))
        try:
            gen, attempts, error = variance.generate_with_retries(variance.CliGenerator(args.model, workdir), prompt)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        return (evaluation.clean_request(gen.text) if gen else None), gen, attempts, error

    def run(task):
        prompt = v5.REQUEST_PROMPT.format(need=task.need)
        rejected = []
        for _ in range(args.attempts):
            text, gen, attempts, error = one(prompt)
            problems = v52.request_problems(text, task)
            if not problems:
                break
            rejected.append({"request": text, "problems": problems, "error": error})
            text = None
        return {"id": task.id, "app": task.app, "need": task.need, "prompt": prompt, "request": text,
                "words": v5.word_count(text) if text else None, "rejected": rejected,
                "model": gen.model if gen else None, "attempts": attempts,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}

    print(f"generating {len(todo)} brief requests ({args.model})")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        fresh = {r["id"]: r for r in pool.map(run, todo)}
    items = [previous.get(t.id) or fresh[t.id] for t in tasks()]
    v5.write_json(target, {"model": args.model, "prompt_template": v5.REQUEST_PROMPT,
                           "rule": "regenerated (fresh process) when it mentions security words or the "
                                   "planted function; see src/pcat/v52.py SECURITY_WORDS", "items": items})
    for r in items:
        print(f"{r['id']}: {r['request']!r} ({r['words']} words; rejected {len(r['rejected'])})")
    failed = [r["id"] for r in items if not r["request"]]
    print(f"{len(items) - len(failed)} ok, {len(failed)} failed {failed}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v5.2 unsafe neighbour")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    vp = sub.add_parser("verify")
    vp.add_argument("--write", action="store_true", help="write experiments/v5.2/verify.json")
    rq = sub.add_parser("requests")
    rq.add_argument("--model", default="claude-sonnet-5-5")
    rq.add_argument("--jobs", type=int, default=4)
    rq.add_argument("--resume", action="store_true")
    rq.add_argument("--attempts", type=int, default=REQUEST_ATTEMPTS)
    r = sub.add_parser("run")
    r.add_argument("--samples", type=int, default=3)
    r.add_argument("--conditions", default="baseline,pcat")
    r.add_argument("--apps", default="")
    r.add_argument("--tasks", default="")
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--cap", type=float, default=40.0, help="stop when the CLI cost estimate exceeds this")
    args = parser.parse_args()
    return {"prepare": cmd_prepare, "verify": cmd_verify, "requests": cmd_requests,
            "run": cmd_run}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
