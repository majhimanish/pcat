"""v5.1: re-score existing data with the fixed linter, and the false-positive survey.

    python scripts/v5_1.py lint-e2e --label LABEL [--jobs 4]
        Rebuild each of v5's 144 end-to-end runs (fresh app copy with the task's
        function removed, committed as the baseline, then the run's saved diff
        applied), lint it exactly as v5 scored it (`pcat lint --changed-since
        <baseline> --include-inferred` on the changed Python files, the app's
        catalog), delete the copy. Output: experiments/v5.1/rescore/e2e_<LABEL>.json.
        Uses whichever `pcat` is importable, so the v5 linter can be run from a git
        worktree of the pre-v5.1 commit: PYTHONPATH=<worktree>/src python scripts/v5_1.py ...
    python scripts/v5_1.py compare-e2e --old LABEL --new LABEL
        Flips and tables -> experiments/v5.1/rescore/e2e_compare.json (+ printed markdown).
    python scripts/v5_1.py compare-samples
        v3-sample replay and v4/v4.1 feedback re-scores (scripts/lint_eval.py with --out under
        experiments/v5.1/rescore/) vs their original scoring -> rescore/samples_compare.json.
    python scripts/v5_1.py survey --label LABEL [--catalogs DIR]
        Lint the untouched app code (pinned commits in .bench/apps; tests, docs and
        migrations excluded) with each app's catalog, --include-inferred.
        Output: experiments/v5.1/survey/survey_<LABEL>.json.

No agent runs: everything here re-scores data that already exists.
The lint step only uses APIs that exist in both the v5 and the v5.1 linter.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V5 = ROOT / "experiments" / "v5"
OUT = ROOT / "experiments" / "v5.1"
APPS_DIR = ROOT / ".bench" / "apps"
RUNS = Path(os.environ.get("PCAT_V51_RUNS", tempfile.gettempdir())) / "pcat-v51-runs"
APPS = ("ctfd", "healthchecks", "lnbits")


def _rescore():
    """src/pcat/rescore.py of this checkout, also when an older `pcat` is on the path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("pcat_v51_rescore", ROOT / "src" / "pcat" / "rescore.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _deviation(d: dict) -> dict:
    return {k: d.get(k) for k in ("code", "severity", "message", "line", "approved", "approval_state")}


def _report(data: dict) -> dict:
    return {
        "failed": data["failed"], "deviations": data["summary"]["deviations"],
        "failing": data["summary"]["failing"], "files": data.get("files"),
        "findings": [{"path": f["path"], "function": f["function"], "line": f["line"], "pattern": f["pattern"],
                      "provenance": f["provenance"], "similarity": f.get("similarity"),
                      "deviations": [_deviation(d) for d in f["deviations"]]}
                     for f in data["findings"]],
        "messages": [m for m in data.get("messages", []) if m.get("level") == "error"],
    }


# --------------------------------------------------------------------------- #
# v5 end-to-end runs
# --------------------------------------------------------------------------- #


def e2e_records() -> list[dict]:
    out = []
    for path in sorted((V5 / "e2e").glob("*/*/*/sample_*.json")):
        rec = json.loads(path.read_text())
        if rec["status"] == "ok":
            out.append({"json": path, "diff": path.with_suffix(".diff"), **{k: rec[k] for k in (
                "app", "task", "condition", "sample", "files_changed")}, "v5_lint": rec["score"]["lint"]})
    return out


def lint_run(rec: dict, tasks: dict) -> dict:
    from pcat import lint, v5

    task = tasks[rec["task"]]
    dest = RUNS / f"{rec['app']}-{rec['task']}-{rec['condition']}-{rec['sample']:02d}"
    try:
        info = v5.prepare_workdir(APPS_DIR / rec["app"], dest, task, rec["condition"])
        diff = rec["diff"].read_text(encoding="utf-8")
        if diff.strip():
            subprocess.run(["git", "-C", str(dest), "apply", "--index", "--whitespace=nowarn", "-"],
                           input=diff, text=True, check=True, capture_output=True)
        py = [str(dest / f) for f in rec["files_changed"] if f.endswith(".py") and (dest / f).exists()]
        key = {k: rec[k] for k in ("app", "task", "condition", "sample")}
        if not py:
            return {**key, "lint": {"failed": False, "deviations": {"high": 0, "medium": 0, "low": 0},
                                    "failing": 0, "findings": [], "messages": []}}
        data = lint.lint_paths(py, V5 / "catalogs" / rec["app"], include_inferred=True,
                               changed_since=info["baseline"]).to_dict()
        report = _report(data)
        for f in report["findings"]:
            f["path"] = Path(f["path"]).resolve().relative_to(dest.resolve()).as_posix()
        return {**key, "lint": report}
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def cmd_lint_e2e(args) -> int:
    import pcat
    from pcat import v5

    tasks = {t.id: t for t in v5.load_tasks(V5 / "tasks.yaml")}
    records = e2e_records()
    print(f"pcat from {Path(pcat.__file__).parent}; {len(records)} runs", flush=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(lambda r: lint_run(r, tasks), records))
    mismatches = [f"{r['app']}/{r['task']}/{r['condition']}/{r['sample']}" for r, rec in zip(rows, records)
                  if args.check_v5 and (r["lint"]["failed"] != rec["v5_lint"]["failed"]
                                        or r["lint"]["deviations"] != rec["v5_lint"]["deviations"])]
    write_json(OUT / "rescore" / f"e2e_{args.label}.json", {
        "label": args.label, "runs": rows,
        "note": "v5's 144 end-to-end runs rebuilt from their saved diffs and linted as v5 scored them",
        **({"differs_from_saved_v5_score": mismatches} if args.check_v5 else {}),
    })
    print(f"{sum(r['lint']['failed'] for r in rows)} runs would fail CI; mismatches vs saved v5 score: "
          f"{len(mismatches) if args.check_v5 else 'not checked'}")
    return 0


def cmd_compare_e2e(args) -> int:
    rescore = _rescore()

    old = json.loads((OUT / "rescore" / f"e2e_{args.old}.json").read_text())
    new = json.loads((OUT / "rescore" / f"e2e_{args.new}.json").read_text())
    result = rescore.compare_e2e(old["runs"], new["runs"])
    write_json(OUT / "rescore" / "e2e_compare.json", {"old": args.old, "new": args.new, **result})
    print(rescore.e2e_markdown(result))
    return 0


LINTER = ROOT / "experiments" / "linter"
SAMPLE_COMPARISONS = {  # name -> (original scoring, v5.1 re-score)
    "v3_samples_vs_v4_replay": (LINTER / "replay.json", OUT / "rescore" / "replay_v3_samples.json"),
    "v3_samples_vs_v4.1_replay": (LINTER / "replay_v4.1.json", OUT / "rescore" / "replay_v3_samples.json"),
    "v4_feedback_vs_v4.1_rescore": (LINTER / "feedback_v4.1" / "v4_rescored.json",
                                    OUT / "rescore" / "feedback_v4.json"),
    "v4.1_feedback_vs_v5_part_a": (LINTER / "feedback_v4.1" / "results.json", OUT / "rescore" / "feedback_v4.1.json"),
}


def cmd_compare_samples(args) -> int:
    """Original scoring vs the v5.1 re-score for the lint_eval.py outputs."""
    rescore = _rescore()
    out = {}
    for name, (old, new) in SAMPLE_COMPARISONS.items():
        r = rescore.compare_samples(json.loads(old.read_text()), json.loads(new.read_text()))
        out[name] = {"original": old.relative_to(ROOT).as_posix(), "rescored": new.relative_to(ROOT).as_posix(), **r}
        print(f"{name}: high {r['high']['old']} -> {r['high']['new']} of {r['samples']}; "
              f"high flips {len(r['high_flips'])}; samples whose codes changed {len(r['changed'])}")
    write_json(OUT / "rescore" / "samples_compare.json", out)
    return 0


# --------------------------------------------------------------------------- #
# False-positive survey on untouched app code
# --------------------------------------------------------------------------- #


def cmd_survey(args) -> int:
    import pcat
    from pcat import lint

    rescore = _rescore()
    print(f"pcat from {Path(pcat.__file__).parent}", flush=True)

    out = {"label": args.label, "apps": {}}
    for app in APPS:
        app_dir = APPS_DIR / app
        files = rescore.survey_files(app_dir)
        data = lint.lint_paths([str(app_dir / f) for f in files], Path(args.catalogs) / app,
                               include_inferred=True).to_dict()
        report = _report(data)
        for f in report["findings"]:
            f["path"] = Path(f["path"]).resolve().relative_to(app_dir.resolve()).as_posix()
        functions = rescore.count_functions(app_dir, files)
        out["apps"][app] = {"files": len(files), "functions_checked": functions,
                            "summary": rescore.survey_summary(report), "findings": report["findings"]}
        s = out["apps"][app]["summary"]
        print(f"{app}: {len(files)} files, {functions} functions, {s['inferred_derived']} inferred derived, "
              f"deviations {s['by_severity']}", flush=True)
    write_json(OUT / "survey" / f"survey_{args.label}.json", out)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="v5.1 re-scoring and survey")
    sub = parser.add_subparsers(dest="command", required=True)
    le = sub.add_parser("lint-e2e")
    le.add_argument("--label", required=True)
    le.add_argument("--jobs", type=int, default=4)
    le.add_argument("--check-v5", action="store_true", help="compare with the score saved in v5")
    ce = sub.add_parser("compare-e2e")
    ce.add_argument("--old", required=True)
    ce.add_argument("--new", required=True)
    sub.add_parser("compare-samples")
    sv = sub.add_parser("survey")
    sv.add_argument("--label", required=True)
    sv.add_argument("--catalogs", default=str(V5 / "catalogs"),
                    help="folder of per-app catalogs (an older checkout's, for an older linter)")
    args = parser.parse_args()
    return {"lint-e2e": cmd_lint_e2e, "compare-e2e": cmd_compare_e2e, "compare-samples": cmd_compare_samples,
            "survey": cmd_survey}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
