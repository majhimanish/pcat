"""v4 evaluation driver (spec docs/specs/v4-linter.md).

    python scripts/lint_eval.py calibrate        # inference threshold (Part A), existing data only
    python scripts/lint_eval.py replay           # lint every v3 sample (no generation); v4.1 rules
                                                 # -> replay_v4.1.json (replay.json = frozen v4 result)
    python scripts/lint_eval.py feedback         # 60 new runs with the v4 server (claude -p)
    python scripts/lint_eval.py feedback-analyze # metrics for the feedback run vs v3

Outputs go to experiments/linter/. Logic lives in src/pcat/linteval.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
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


# --------------------------------------------------------------------------- #
# Replay (no generation)
# --------------------------------------------------------------------------- #

LIBRARY_ROOTS = ("pandas", "openpyxl", "polars", "xlrd")


def score_code(code: str, pattern_id: str, service: CatalogService) -> dict:
    """Lint one sample's final code against `pattern_id` (markers win if present)."""
    result = service.check_code(code, pattern_id)
    analyses = [a for a in result.get("deviations", [])]
    roots = set(evaluation.import_roots(code))
    return {
        "analyses": analyses,
        "codes": linteval.codes(analyses),
        "high_codes": linteval.high_codes(analyses),
        "worst": linteval.worst(analyses),
        "worst_including_approved": linteval.worst(analyses, approved=True),
        "approvals": sorted({(d["code"], d["approval"]) for a in analyses for d in a["deviations"]
                             if d["approved"]}),
        "switched_library": bool(roots & set(LIBRARY_ROOTS)) and "csv" not in roots,
        "third_party": sorted(roots & set(LIBRARY_ROOTS)),
        "marked": any(f.get("marker") for f in result.get("functions", [])),
    }


def cmd_replay(args) -> int:
    service = CatalogService(ROOT)
    tasks = evaluation.cataloged_tasks(ROOT)
    v3 = json.loads((ROOT / "experiments" / "mcp" / "e2e_results.json").read_text())
    rows = []
    for task, pattern_id in tasks.items():
        outcomes = {s["sample"]: s["outcome"] for s in v3["tasks"][task]["samples"]}
        for rec in _records(task):
            fetched = linteval.fetched_patterns(rec["tool_calls"])
            target = pattern_id if pattern_id in fetched else (fetched[-1] if fetched else pattern_id)
            scored = score_code(rec["code"], target, service)
            rows.append({"task": task, "sample": rec["sample"], "pattern": target,
                         "outcome": outcomes[rec["sample"]], **scored})
    negatives = []
    for rec in _records("negative"):
        for pid in linteval.fetched_patterns(rec["tool_calls"]):
            negatives.append({"task": "negative", "sample": rec["sample"], "pattern": pid,
                              "outcome": "negative", **score_code(rec["code"], pid, service)})
    calib = json.loads((OUT / "inference_calibration.json").read_text())
    by_source: dict[str, list[dict]] = {}
    for item in calib["items"]:
        group = "v3 derived" if item["expected"] else (
            "v2.1 FastAPI (not derived)" if item["source"].startswith("v2.1") else "v3 negatives (not derived)")
        by_source.setdefault(group, []).append(item)
    inference = {g: linteval.inference_summary(items, provenance.INFERENCE_THRESHOLD)
                 for g, items in sorted(by_source.items())}
    inference["all"] = calib["summary"]
    report = {
        "checks": linteval.replay_checks(rows),
        "confusion": linteval.confusion(rows),
        "inference": inference,
        "samples": rows,
        "negatives_that_fetched": negatives,
    }
    write_json(OUT / args.out, report)
    print(json.dumps({"checks": report["checks"], "confusion": report["confusion"]}, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# Feedback run (new generation with the v4 server)
# --------------------------------------------------------------------------- #

FEEDBACK = OUT / "feedback"
FEEDBACK_TASKS = ("http_retry", "csv_import", "paginate_query")


def _mcp_eval(out_dir: Path = FEEDBACK):
    """scripts/mcp_eval.py as a module: the v3 end-to-end setup, reused unchanged."""
    spec = importlib.util.spec_from_file_location("mcp_eval", ROOT / "scripts" / "mcp_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.E2E = out_dir  # write under experiments/linter/<dir>/, never to the v3 data
    return module


def cmd_feedback(args) -> int:
    feedback_dir = OUT / args.dir
    me = _mcp_eval(feedback_dir)
    groups = args.groups.split(",") if args.groups else list(FEEDBACK_TASKS)
    jobs = [j for j in me.e2e_jobs(args.samples, 0) if j["group"] in groups]
    if args.only:
        jobs = [j for j in jobs if j["sample"] in {int(x) for x in args.only.split(",")}]
    todo = []
    for job in jobs:
        path = feedback_dir / job["group"] / f"sample_{job['sample']:02d}.json"
        if path.exists() and json.loads(path.read_text())["status"] == "ok":
            continue
        job.update(model=args.model, pcat=str(Path(sys.executable).parent / "pcat"))
        todo.append(job)
    print(f"running {len(todo)} feedback samples ({len(jobs) - len(todo)} already done)")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for n, r in enumerate(pool.map(me._e2e_job, todo), 1):
            tools = [c["tool"] for c in r["tool_calls"]]
            print(f"[{n}/{len(todo)}] {r['group']} #{r['sample']:02d} {r['status']} tools={tools}", flush=True)
    return 0


def cmd_feedback_analyze(args) -> int:
    from pcat import catalog as cat

    service = CatalogService(ROOT)
    tasks = evaluation.cataloged_tasks(ROOT)
    v3 = json.loads((ROOT / "experiments" / "mcp" / "e2e_results.json").read_text())
    replay = json.loads((OUT / args.replay).read_text())
    feedback_dir = OUT / args.dir
    results: dict = {"note": f"feedback run in {args.dir}/, scored with the current rules; v3 baseline "
                             f"from {args.replay}; cost is the CLI's estimate and may reflect plan usage",
                     "tasks": {}}
    total_cost = 0.0
    for task in FEEDBACK_TASKS:
        pattern_id = tasks[task]
        pattern = cat.get_one(ROOT, pattern_id)
        functions = [pattern.meta.entry_point, *pattern.meta.exports]
        rows = []
        for path in sorted((feedback_dir / task).glob("sample_*.json")):
            rec = json.loads(path.read_text())
            if rec["status"] != "ok":
                rows.append({"sample": rec["sample"], "status": rec["status"]})
                continue
            calls = evaluation.tool_calls(rec["tool_calls"])
            check = service.check_code(rec["code"] or "")
            match = evaluation.pattern_match(check, pattern_id, functions)
            fetched = linteval.fetched_patterns(rec["tool_calls"])
            scored = score_code(rec["code"] or "", pattern_id, service)
            checks = calls["check_code"]
            rows.append({
                "sample": rec["sample"], "status": "ok", "request": rec["request"],
                "searched": bool(calls["search_patterns"]), "retrieved": pattern_id in fetched,
                "check_calls": len(checks),
                "checked_with_pattern_id": any(c["arguments"].get("pattern_id") for c in checks),
                "high_seen_in_check": any(code == "PC100" or code in ("PC101", "PC102", "PC103")
                                          for c in checks for _, _, devs in c["result"].get("deviations", [])
                                          for code, _ in devs),
                "match_shape": match["shape"], "match_exact": match["exact"],
                "cost_usd": rec["extra"].get("cost_usd"), "turns": rec["extra"].get("num_turns"),
                **{k: scored[k] for k in ("codes", "high_codes", "worst", "worst_including_approved",
                                          "approvals", "marked", "third_party")},
                "approval_lines": linteval.approval_census(rec["code"] or ""),
                "worst_not_proposed": linteval.worst_not_proposed(scored["analyses"]),
            })
        ok = [r for r in rows if r["status"] == "ok"]
        n = len(ok) or 1
        cost = sum(r["cost_usd"] or 0 for r in ok)
        total_cost += cost
        v3_rows = [r for r in replay["samples"] if r["task"] == task]
        summary = {
            "samples": len(rows), "ok": len(ok),
            "pattern_match_shape": round(sum(r["match_shape"] for r in ok) / n, 3),
            "pattern_match_exact": round(sum(r["match_exact"] for r in ok) / n, 3),
            "unapproved_high_samples": sum(r["worst"] == "high" for r in ok),
            "approved_samples": sum(bool(r["approvals"]) for r in ok),
            "kept_marker": sum(r["marked"] for r in ok),
            "check_rate": round(sum(r["check_calls"] > 0 for r in ok) / n, 3),
            "check_with_pattern_id_rate": round(sum(r["checked_with_pattern_id"] for r in ok) / n, 3),
            "mean_check_calls": round(sum(r["check_calls"] for r in ok) / n, 2),
            "cost_usd": round(cost, 4),
            "v3_pattern_match_shape": v3["tasks"][task]["summary"]["pattern_match_shape"],
            "v3_unapproved_high_samples": sum(r["worst"] == "high" for r in v3_rows),
            "v3_worst": {s: sum(r["worst"] == s for r in v3_rows) for s in linteval.SEVERITIES},
            "worst": {s: sum(r["worst"] == s for r in ok) for s in linteval.SEVERITIES},
            "approval_codes": sorted({c for r in ok for c, _ in r["approvals"]}),
            "high_not_covered_by_a_proposal_samples": sum(r["worst_not_proposed"] == "high" for r in ok),
            "approval_lines": {state: sum(1 for r in ok for a in r["approval_lines"] if a["state"] == state)
                               for state in linteval.CENSUS_STATES},
            "samples_with_approval_lines": sum(bool(r["approval_lines"]) for r in ok),
        }
        results["tasks"][task] = {"pattern": pattern_id, "summary": summary, "samples": rows}
    results["total_cost_usd_estimate"] = round(total_cost, 2)
    if (OUT / args.out).resolve() == (OUT / "feedback_results.json").resolve():
        sys.exit("feedback_results.json is the frozen v4 result; pass another --out")
    write_json(OUT / args.out, results)
    print("| Task | v3 match | match | v3 high unapproved | high unapproved | approved | check w/ id | cost |")
    print("|---|---|---|---|---|---|---|---|")
    for task, data in results["tasks"].items():
        s = data["summary"]
        print(f"| {task} | {s['v3_pattern_match_shape']:.2f} | {s['pattern_match_shape']:.2f} | "
              f"{s['v3_unapproved_high_samples']}/20 | {s['unapproved_high_samples']}/{s['ok']} | "
              f"{s['approved_samples']}/{s['ok']} | {s['check_with_pattern_id_rate']:.2f} | ${s['cost_usd']} |")
    print(f"total cost estimate ${results['total_cost_usd_estimate']}")
    return 0


def main() -> int:
    from pcat import variance

    parser = argparse.ArgumentParser(description="v4 evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("calibrate")
    rp = sub.add_parser("replay")
    rp.add_argument("--out", default="replay_v4.1.json",
                    help="file under experiments/linter/ (replay.json is the frozen v4 result)")
    fa = sub.add_parser("feedback-analyze")
    fa.add_argument("--dir", default="feedback", help="samples under experiments/linter/<dir>/")
    fa.add_argument("--out", required=True, help="file under experiments/linter/")
    fa.add_argument("--replay", default="replay_v4.1.json", help="v3 baseline replay file")
    f = sub.add_parser("feedback")
    f.add_argument("--dir", default="feedback", help="output under experiments/linter/<dir>/")
    f.add_argument("--samples", type=int, default=20)
    f.add_argument("--groups", default="")
    f.add_argument("--only", default="", help="comma-separated sample numbers")
    f.add_argument("--model", default=variance.DEFAULT_MODEL)
    f.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    return {"calibrate": cmd_calibrate, "replay": cmd_replay, "feedback": cmd_feedback,
            "feedback-analyze": cmd_feedback_analyze}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
