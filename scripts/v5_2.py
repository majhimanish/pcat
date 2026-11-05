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

import _labpath  # noqa: F401  (experiments/lib on sys.path)

import argparse
import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V52 = ROOT / "experiments" / "v5.2"
V5 = ROOT / "experiments" / "v5"
APPS_DIR = ROOT / ".bench" / "apps"


def tasks():
    from pcatlab import v52

    return v52.load_tasks(V52 / "tasks.yaml")


def catalog_pattern(app: str, pattern_id: str):
    from pcat import catalog as cat

    return cat.get_one(V5 / "catalogs" / app, pattern_id)


_PATTERNS: dict[str, dict] = {}


def catalog_patterns(app: str) -> dict:
    """pattern id -> active Pattern of the app's catalog (cached)."""
    from pcat import catalog as cat

    if app not in _PATTERNS:
        _PATTERNS[app] = {p.meta.id: p for p in cat.load_catalog(V5 / "catalogs" / app)
                          if p.meta is not None and p.meta.status == "active"}
    return _PATTERNS[app]


def cmd_prepare(args) -> int:
    from pcatlab import v5, v52

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
    from pcatlab import v52

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
    from pcatlab import v5, v52

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

    from pcatlab import v5, v52

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


# --------------------------------------------------------------------------- #
# Part D: scoring (rebuild each run from its diff, as in v5.1)
# --------------------------------------------------------------------------- #


def rebuild(task, record: dict, plant: bool, dest: Path) -> Path:
    import subprocess

    from pcatlab import v5, v52

    if plant:
        v52.prepare_workdir(APPS_DIR / task.app, dest, task, record["condition"], v52.neighbour_code(ROOT, task))
    else:  # a v5 run: no neighbour
        v5.prepare_workdir(APPS_DIR / task.app, dest, task.as_v5(), record["condition"])
    diff = Path(record["_diff"]).read_text(encoding="utf-8")
    if diff.strip():
        subprocess.run(["git", "-C", str(dest), "apply", "--index", "--whitespace=nowarn", "-"],
                       input=diff, text=True, check=True, capture_output=True)
    return dest


def score_run(task, record: dict, plant: bool = True) -> dict:
    import gzip
    import shutil
    import subprocess

    from pcat import codeunit, lint, provenance
    from pcatlab import derivation, v5, v52
    from pcat.serving import CatalogService

    catalog_root = V5 / "catalogs" / task.app
    pattern = catalog_pattern(task.app, task.pattern)
    dest = RUNS / f"score-{task.app}-{task.id}-{record['condition']}-{record['sample']:02d}-{int(plant)}"
    try:
        rebuild(task, record, plant, dest)
        files = record["files_changed"]
        reference = (V52 / "references" / task.app / f"{task.id}.py").read_text(encoding="utf-8")
        matched = v52.match_new_functions(dest, task, files, reference)
        sources = {m["path"]: (dest / m["path"]).read_text(encoding="utf-8") for m in matched.values()}
        g = v52.guard_outcome(task, matched, sources, pattern, lambda rel: codeunit.module_for_path(dest / rel))
        # pattern use
        fetched = [f.split("@")[0] for f in record["tool_order"]["fetched"]]
        statuses, marks, derived = [], [], []
        refs = provenance.references(catalog_root)
        service = CatalogService(catalog_root)
        for path, src in sorted(sources.items()):
            check = service.check_code(src)
            nodes = {(m["node"].lineno) for m in matched.values() if m["path"] == path}
            statuses += [f for f in check["functions"] if f["line"] in nodes]
            for info in provenance.functions(src):
                if info.node.lineno in nodes:
                    marks.append(info.marker.ref if info.marker else None)
                    inf = provenance.infer(info.node, refs)
                    derived.append(bool(inf and inf.derived and inf.pattern_id == task.pattern))
        pid = task.pattern
        use = {"searched": record["tool_order"]["searched"], "fetched_right": pid in fetched,
               "fetched": record["tool_order"]["fetched"],
               "matches_pattern": any(f["status"] in ("covered", "near") and f["pattern"] == pid for f in statuses),
               "marked": any(m and m.split("@")[0] == pid for m in marks),
               "derives": any(m and m.split("@")[0] == pid for m in marks) or any(derived)}
        # neighbour behaviour
        nb = {}
        if plant:
            with gzip.open(Path(record["_diff"]).with_suffix(".transcript.jsonl.gz"), "rt") as fh:
                lines = fh.read().splitlines()
            code = v52.neighbour_code(ROOT, task)
            nb = v52.neighbour_behavior(task, lines)
            nb["changed"] = v52.neighbour_changed(dest, task, code)
            planted_node = next(n for n in ast.parse(code).body if isinstance(n, codeunit.FUNC_TYPES))
            p_tree = ast.parse(pattern.impl_path.read_text(encoding="utf-8"))
            p_node = next(n for n in p_tree.body if isinstance(n, codeunit.FUNC_TYPES)
                          and n.name == task.neighbour.pattern_function)
            mine = [m["node"] for fn, m in matched.items() if task.target_map[fn] == task.neighbour.pattern_function]
            nb["similarity_to_neighbour"] = max((v52.similarity(x, planted_node) for x in mine), default=None)
            nb["similarity_to_pattern"] = max((v52.similarity(x, p_node) for x in mine), default=None)
            nb["literal_similarity_to_neighbour"] = max((v52.literal_similarity(x, planted_node) for x in mine),
                                                        default=None)
            nb["literal_similarity_to_pattern"] = max((v52.literal_similarity(x, p_node) for x in mine), default=None)
            nb["imitated"] = any(v52.imitates(x, planted_node, p_node) for x in mine)
        # what real CI would do (v5.1 recommendation: marked code fails, inferred is advisory)
        py = [str(dest / f) for f in files if f.endswith(".py") and (dest / f).exists()]
        base = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
        ci = {"failed": False, "catches_inherited": False, "advisory_flags_inherited": False, "failing": []}
        mode = {"failed": False, "catches_inherited": False, "failing": []}
        if py:
            opted = lint.lint_paths(py, catalog_root, include_inferred=True, changed_since=base,
                                    fail_on_inferred_guards=True)
            mode["failed"] = opted.failed
            wanted_m = {(m["path"], m["function"]) for fn, m in matched.items()
                        if task.target_map[fn] == task.neighbour.pattern_function}
            for f in opted.findings:
                rel = Path(f.path).resolve().relative_to(dest.resolve()).as_posix()
                failing = f.failing("high")
                mode["failing"] += [f"{f.function}: {d['code']} ({f.provenance})" for d in failing]
                if (rel, f.function) in wanted_m and g["flaw_inherited"] and any(d["code"] == "PC100" for d in failing):
                    mode["catches_inherited"] = True
            report = lint.lint_paths(py, catalog_root, include_inferred=True, changed_since=base)
            ci["failed"] = report.failed
            wanted = {(m["path"], m["function"]) for fn, m in matched.items()
                      if task.target_map[fn] == task.neighbour.pattern_function}
            for f in report.findings:
                rel = Path(f.path).resolve().relative_to(dest.resolve()).as_posix()
                failing = f.failing("high")
                ci["failing"] += [f"{f.function}: {d['code']}" for d in failing]
                if (rel, f.function) in wanted and g["flaw_inherited"]:
                    pc100 = [d for d in f.deviations if d["code"] == "PC100"]
                    if any(d in failing for d in pc100):
                        ci["catches_inherited"] = True
                    elif pc100:
                        ci["advisory_flags_inherited"] = True
        # Part E: derivation features of each function written for a pattern entry point or export
        patterns = catalog_patterns(task.app)
        public = {pattern.meta.entry_point, *pattern.meta.exports}
        for fn, m in matched.items():
            if task.target_map[fn] in public:
                tree = ast.parse(sources[m["path"]])
                node = next(n for n in ast.walk(tree) if isinstance(n, codeunit.FUNC_TYPES)
                            and n.lineno == m["node"].lineno and n.name == m["node"].name)
                m["features"] = derivation.features(tree, node, codeunit.module_for_path(dest / m["path"]),
                                                    refs, patterns, label_pattern=task.pattern)
        for o in g["targets"].values():
            o.pop("node", None)
        return {"app": task.app, "task": task.id, "condition": record["condition"], "sample": record["sample"],
                "status": record["status"], "cost_usd": record["summary"].get("cost_usd"),
                "wall_seconds": record["wall_seconds"], "files_changed": files, "guards": g, "use": use,
                "neighbour": nb, "ci": ci, "ci_inferred_guards": mode,
                "new_functions": {fn: {k: v for k, v in m.items() if k != "node"} for fn, m in matched.items()}}
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def load_runs(base: Path, task_dir) -> list[dict]:
    out = []
    for path in sorted(base.glob(f"{task_dir}/*/sample_*.json")):
        rec = json.loads(path.read_text())
        rec["_diff"] = str(path.with_suffix(".diff"))
        out.append(rec)
    return out


def cmd_analyze(args) -> int:
    from concurrent.futures import ThreadPoolExecutor

    from pcatlab import v5, v52

    RUNS.mkdir(parents=True, exist_ok=True)
    jobs_ = [(t, rec, True) for t in tasks() for rec in load_runs(E2E, f"{t.app}/{t.id}")]
    jobs_ += [(t, rec, False) for t in tasks() if t.v5_task
              for rec in load_runs(V5 / "e2e", f"{t.app}/{t.v5_task}") if rec["status"] == "ok"]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        scored = list(pool.map(lambda j: (j[2], score_run(*j)), jobs_))
    rows = [r for plant, r in scored if plant]
    v5_rows = [r for plant, r in scored if not plant]
    out: dict = {"note": "v5.2 end-to-end, scored by rebuilding each run from its diff; guards of the task's "
                         "pattern applied to the functions the run wrote; cost is the CLI's estimate and may "
                         "reflect plan usage", "apps": {}, "per_task": {}, "v5_comparison": {}}
    for app in sorted({r["app"] for r in rows}):
        out["apps"][app] = {c: v52.summarize([r for r in rows if r["app"] == app and r["condition"] == c])
                            for c in ("baseline", "pcat")}
    out["all"] = {c: v52.summarize([r for r in rows if r["condition"] == c]) for c in ("baseline", "pcat")}
    for t in tasks():
        out["per_task"][t.id] = {c: v52.summarize([r for r in rows if r["task"] == t.id and r["condition"] == c])
                                 for c in ("baseline", "pcat")}
        if t.v5_task:
            mine = [r for r in v5_rows if r["task"] == t.id]
            out["v5_comparison"][t.id] = {c: {
                "v5_runs": sum(r["condition"] == c for r in mine),
                "v5_neighbour_flaw": sum(r["guards"]["flaw_inherited"] for r in mine if r["condition"] == c),
                "v5_any_guard_violated": sum(r["guards"]["any_guard_violated"] for r in mine if r["condition"] == c),
                "v52_runs": out["per_task"][t.id][c]["ok"],
                "v52_flaw_inherited": out["per_task"][t.id][c]["flaw_inherited"],
                "v52_any_guard_violated": out["per_task"][t.id][c]["any_guard_violated"]}
                for c in ("baseline", "pcat")}
    out["runs"] = rows
    out["v5_runs_rescored"] = v5_rows
    v5.write_json(V52 / "results.json", out)
    keys = ["ok", "flaw_inherited", "any_guard_violated", "searched", "fetched_right", "matches_pattern",
            "derives", "saw_neighbour", "imitated_neighbour", "flagged_neighbour", "ci_fails",
            "ci_catches_inherited", "ci_misses_inherited_unmarked", "total_cost_usd"]
    print("| App | Condition | " + " | ".join(keys) + " |")
    print("|---|---|" + "---|" * len(keys))
    for app, conds in [*out["apps"].items(), ("all", out["all"])]:
        for c, s_ in conds.items():
            print(f"| {app} | {c} | " + " | ".join(str(s_[k]) for k in keys) + " |")
    return 0


# --------------------------------------------------------------------------- #
# Part E: a labeled set for "is F derived from P?" and inference variants
# --------------------------------------------------------------------------- #

INF = V52 / "inference"
RANDOM_PER_APP = 40


def _function_in(path: Path, qualname: str):
    from pcat import provenance

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for info in provenance.functions(source, tree):
        if info.qualname == qualname:
            return tree, info.node
    return None, None


def _untouched_item(app, rel, qualname, source, label, label_pattern, ident=None):
    from pcat import codeunit, provenance
    from pcatlab import derivation

    path = APPS_DIR / app / rel
    tree, node = _function_in(path, qualname)
    if node is None:
        return None
    refs = _refs(app)
    feats = derivation.features(tree, node, codeunit.module_for_path(path), refs, catalog_patterns(app),
                                label_pattern)
    group = f"{app}/{label_pattern if label else feats.get('best_pattern')}"
    return derivation.Item(ident or f"{app}:{rel}::{qualname}", app, source, group, label, label_pattern, feats)


_REFS: dict[str, list] = {}


def _refs(app: str):
    from pcat import provenance

    if app not in _REFS:
        _REFS[app] = provenance.references(V5 / "catalogs" / app)
    return _REFS[app]


def _v5_run_item(task, rec):
    """The function a v5 run wrote (v5's own matching), labeled by its task."""
    import shutil

    from pcat import codeunit
    from pcatlab import derivation, v5

    dest = RUNS / f"label-{task.app}-{task.id}-{rec['condition']}-{rec['sample']:02d}"
    try:
        v5.prepare_workdir(APPS_DIR / task.app, dest, task, rec["condition"])
        diff = Path(rec["_diff"]).read_text(encoding="utf-8")
        if diff.strip():
            import subprocess
            subprocess.run(["git", "-C", str(dest), "apply", "--index", "--whitespace=nowarn", "-"],
                           input=diff, text=True, check=True, capture_output=True)
        reference = (V5 / "references" / task.app / f"{task.id}.py").read_text(encoding="utf-8")
        found = v5.find_new_function(dest, task, rec["files_changed"], reference)
        if found is None:
            return None
        path = dest / found["path"]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in ast.walk(tree) if isinstance(n, codeunit.FUNC_TYPES)
                    and n.lineno == found["node"].lineno and n.name == found["node"].name)
        feats = derivation.features(tree, node, codeunit.module_for_path(path), _refs(task.app),
                                    catalog_patterns(task.app), task.pattern)
        label = task.kind == "pattern"
        group = f"{task.app}/{task.pattern if label else feats.get('best_pattern')}"
        return derivation.Item(f"v5:{task.app}/{task.id}/{rec['condition']}/{rec['sample']}", task.app,
                               "v5 run", group, label, task.pattern, feats)
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def build_items(jobs_: int = 4) -> list:
    import random
    from concurrent.futures import ThreadPoolExecutor

    from pcatlab import derivation, rescore, v5

    items, seen = [], set()

    def add(item, key=None):
        if item is not None and (key is None or key not in seen):
            items.append(item)
            if key is not None:
                seen.add(key)

    # 1. untouched originals of v5 and v5.2 tasks (derived from their pattern; v5 negatives: from none)
    for t in v5.load_tasks(V5 / "tasks.yaml"):
        key = (t.app, t.file, t.entry)
        add(_untouched_item(t.app, t.file, t.entry, "original", t.kind == "pattern", t.pattern), key)
    for t in tasks():
        public = {catalog_pattern(t.app, t.pattern).meta.entry_point, *catalog_pattern(t.app, t.pattern).meta.exports}
        for fn, pfn in t.targets:
            if pfn in public:
                add(_untouched_item(t.app, t.file, fn, "original", True, t.pattern), (t.app, t.file, fn))
    # 2. v5.1's hand-classified survey findings (debatable = a real sibling, false positive = not derived)
    survey = json.loads((ROOT / "experiments" / "v5.1" / "survey" / "classification.json").read_text())
    for app, data in sorted(survey["apps"].items()):
        for it in data["items"]:
            if "second time" in it["reason"]:
                continue  # a nested wrapper of an already-derived function: neither label fits
            label = it["verdict"] in ("true deviation", "debatable")
            pid = it["pattern"].split("@")[0]
            add(_untouched_item(app, it["path"], it["function"], "v5.1 survey", label, pid if label else None),
                (app, it["path"], it["function"]))
    # 3. a random sample of other app functions (assumed not derived)
    for app in ("ctfd", "healthchecks", "lnbits"):
        from pcat import provenance

        pool = []
        for rel in rescore.survey_files(APPS_DIR / app):
            try:
                source = (APPS_DIR / app / rel).read_text(encoding="utf-8")
                infos = provenance.functions(source, ast.parse(source))
            except (SyntaxError, ValueError, UnicodeDecodeError):
                continue
            pool += [(rel, i.qualname) for i in infos if (app, rel, i.qualname) not in seen]
        for rel, qualname in random.Random(f"v5.2-{app}").sample(pool, RANDOM_PER_APP):
            add(_untouched_item(app, rel, qualname, "random app function", False, None), (app, rel, qualname))
    # 4. v5 runs (pattern tasks: derived from the task's pattern; negatives: from none)
    v5_tasks = {t.id: t for t in v5.load_tasks(V5 / "tasks.yaml")}
    v5_jobs = [(v5_tasks[r["task"]], r) for r in load_runs(V5 / "e2e", "*/*") if r["status"] == "ok"]
    with ThreadPoolExecutor(max_workers=jobs_) as pool_:
        for item in pool_.map(lambda j: _v5_run_item(*j), v5_jobs):
            add(item)
    # 5. v5.2 runs (features recorded by `analyze`)
    results = json.loads((V52 / "results.json").read_text())
    by_id = {t.id: t for t in tasks()}
    for r in results["runs"]:
        t = by_id[r["task"]]
        for fn, m in sorted(r["new_functions"].items()):
            if "features" in m:
                add(derivation.Item(f"v5.2:{r['app']}/{r['task']}/{r['condition']}/{r['sample']}/{fn}", r["app"],
                                    "v5.2 run", f"{r['app']}/{t.pattern}", True, t.pattern, m["features"]))
    return items


def cmd_labels(args) -> int:
    from dataclasses import asdict

    from pcatlab import v5

    RUNS.mkdir(parents=True, exist_ok=True)
    items = build_items(args.jobs)
    v5.write_json(INF / "labeled.json", {
        "note": "Part E labeled set: is the function derived from label_pattern (label true) or from no "
                "pattern (false)? Features are against the most similar catalog function.",
        "items": sorted((asdict(i) for i in items), key=lambda x: x["id"])})
    from collections import Counter
    print(Counter((i.source, i.label) for i in items))
    return 0


def cmd_calibrate(args) -> int:
    from pcatlab import derivation, v5

    raw = json.loads((INF / "labeled.json").read_text())["items"]
    items = [derivation.Item(**r) for r in raw]
    halves = derivation.split(items)
    for name, half in halves.items():
        print(f"{name}: {len(half)} items, {sum(i.label for i in half)} derived, groups "
              f"{len({i.group for i in half})}")
    best, scored_cal = derivation.choose(halves["calibration"])
    held = {n: derivation.evaluate(halves["held_out"], p) for n, p in derivation.variants().items()}
    out = {"split": {n: {"items": len(h), "positives": sum(i.label for i in h),
                         "groups": sorted({i.group for i in h})} for n, h in halves.items()},
           "calibration": scored_cal, "held_out": held, "chosen": best,
           "chosen_held_out": held[best], "default_held_out": held["sim>=0.56"],
           "bar": {"precision": 0.9, "recall": 0.5}}
    hp = held[best]
    out["meets_bar"] = bool(hp["precision"] is not None and hp["precision"] >= 0.9 and (hp["recall"] or 0) >= 0.5)
    v5.write_json(INF / "calibration.json", out)
    print("| Variant | calibration P | R | held-out P | R |")
    print("|---|---|---|---|---|")
    for n in derivation.variants():
        c, h = scored_cal[n], held[n]
        print(f"| {n}{' (chosen)' if n == best else ''} | {c['precision']} | {c['recall']} | {h['precision']} | {h['recall']} |")
    print(f"chosen {best}: held-out {hp}; meets bar: {out['meets_bar']}")
    return 0


REQUEST_ATTEMPTS = 3  # fresh processes per task when a request mentions security or the neighbour


def cmd_requests(args) -> int:
    import datetime as dt
    import shutil
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    from pcatlab import evaluation, v5, v52, variance

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
                                   "planted function; see experiments/lib/pcatlab/v52.py SECURITY_WORDS", "items": items})
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
    lb = sub.add_parser("labels")
    lb.add_argument("--jobs", type=int, default=4)
    sub.add_parser("calibrate")
    an = sub.add_parser("analyze")
    an.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    return {"prepare": cmd_prepare, "verify": cmd_verify, "requests": cmd_requests,
            "run": cmd_run, "analyze": cmd_analyze, "labels": cmd_labels,
            "calibrate": cmd_calibrate}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
