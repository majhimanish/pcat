"""LLM output variance experiment driver (spec docs/specs/v2.1-variance-experiment.md).

    python scripts/variance.py generate --run-id main --conditions A,B [--samples 20] [--tasks t1,t2]
    python scripts/variance.py analyze --run-id main
    python scripts/variance.py reference --run-id main        # picks condition C references from B
    python scripts/variance.py generate --run-id main --conditions C
    python scripts/variance.py report --run-id main

Samples go to experiments/variance/runs/<run-id>/<task>/<condition>/sample_NN.{py,json}.
Every sample is generated in a fresh context (one API request or one `claude -p`
process in a new empty directory). Existing successful samples are skipped, so
an interrupted run can be resumed. Logic lives in src/pcat/variance.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pcat import miner, variance

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "variance"
TASKS_FILE = EXP / "tasks.yaml"
REFS = EXP / "references"


def run_dir(run_id: str) -> Path:
    return EXP / "runs" / run_id


def make_generator(args):
    backend = args.backend if args.backend != "auto" else variance.select_backend()
    if backend == "api":
        return variance.ApiGenerator(args.model, os.environ["ANTHROPIC_API_KEY"])
    if backend == "cli":
        return variance.CliGenerator(args.model, Path(tempfile.gettempdir()))
    sys.exit(
        "No generator backend: set ANTHROPIC_API_KEY (Anthropic API) or install the Claude "
        "CLI (`claude -p`). The third backend, fresh subagents, has to be driven by a Claude "
        "session: one new subagent per sample, given only the prompt, storing files in the "
        "same layout. See docs/benchmarks/v2.1-variance.md."
    )


def load_reference(task: str) -> str:
    path = REFS / f"{task}.py"
    if not path.is_file():
        sys.exit(f"missing reference {path.relative_to(ROOT)}; run `reference` first")
    return path.read_text(encoding="utf-8")


def one_sample(generator, job: dict) -> dict:
    """Generate, extract and store one sample. Never raises for generation errors."""
    if isinstance(generator, variance.CliGenerator):
        # A new empty directory per sample: nothing on disk for the model to see.
        workdir = Path(tempfile.mkdtemp(prefix="pcat-variance-"))
        generator = variance.CliGenerator(generator.model, workdir, generator.timeout)
    else:
        workdir = None
    try:
        gen, attempts, error = variance.generate_with_retries(generator, job["prompt"])
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
    record = {
        "task": job["task"],
        "condition": job["condition"],
        "sample": job["number"],
        "prompt": job["prompt"],
        "prompt_variant": job["variant"],
        "backend": generator.backend,
        "requested_model": generator.model,
        "model": gen.model if gen else None,
        "temperature": gen.temperature if gen else None,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "attempts": attempts,
        "status": "ok" if gen else "failed",
        "error": error,
        "raw_response": gen.text if gen else None,
        "extra": gen.extra if gen else {},
    }
    if gen:
        code = variance.extract_code(gen.text)
        reason = variance.check_code(code)
        record.update({"code": code, "valid": reason is None, "invalid_reason": reason})
        job["py"].write_text(code, encoding="utf-8")
    job["json"].write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def cmd_generate(args) -> int:
    tasks = variance.load_tasks(TASKS_FILE)
    names = args.tasks.split(",") if args.tasks else list(tasks["tasks"])
    out = run_dir(args.run_id)
    jobs = []
    for condition in args.conditions.split(","):
        for task in names:
            reference = load_reference(task) if condition == "C" else None
            for i in range(args.samples):
                py, js = variance.sample_paths(out, task, condition, i + 1)
                if js.is_file() and json.loads(js.read_text())["status"] == "ok":
                    continue
                prompt, variant = variance.build_prompt(tasks, task, condition, i, reference)
                py.parent.mkdir(parents=True, exist_ok=True)
                jobs.append({"task": task, "condition": condition, "number": i + 1,
                             "prompt": prompt, "variant": variant, "py": py, "json": js})
    if not jobs:
        print("nothing to generate")
        return 0
    generator = make_generator(args)
    print(f"generating {len(jobs)} sample(s) with backend {generator.backend}, "
          f"model {generator.model}, {args.jobs} in parallel")
    failed = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(one_sample, generator, job) for job in jobs]
        for done, future in enumerate(as_completed(futures), 1):
            r = future.result()
            mark = "ok" if r["status"] == "ok" else f"FAILED ({r['error']})"
            if r["status"] == "ok" and not r["valid"]:
                mark = f"invalid ({r['invalid_reason']})"
            failed += r["status"] != "ok"
            print(f"[{done}/{len(jobs)}] {r['task']} {r['condition']} #{r['sample']:02d}: {mark}",
                  flush=True)
    print(f"done: {len(jobs) - failed} generated, {failed} failed permanently")
    return 0


def load_references() -> dict:
    path = REFS / "references.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def cmd_analyze(args) -> int:
    tasks = list(variance.load_tasks(TASKS_FILE)["tasks"])
    out = run_dir(args.run_id)
    analysis = variance.analyze_run(out, tasks, load_references())
    (out / "analysis.json").write_text(variance.analysis_json_text(analysis), encoding="utf-8")
    (out / "table.md").write_text(variance.headline_table(analysis), encoding="utf-8")
    print(variance.headline_table(analysis), end="")
    if not args.no_mine:
        settings = miner.MineSettings(min_occurrences=1, include_trivial=True)
        for condition in variance.CONDITIONS:
            inputs = [
                str((out / t / condition).relative_to(ROOT))
                for t in tasks
                if (out / t / condition).is_dir()
            ]
            if not inputs:
                continue
            cwd = os.getcwd()
            os.chdir(ROOT)  # inputs are recorded relative to the repo root
            try:
                result = miner.mine(inputs, settings, cache_dir=None, catalog_root=ROOT)
            finally:
                os.chdir(cwd)
            miner.write_report(result.report, out / f"mine-{condition}")
            print(f"mined condition {condition}: report in {(out / f'mine-{condition}').relative_to(ROOT)}/")
    return 0


def cmd_reference(args) -> int:
    tasks = list(variance.load_tasks(TASKS_FILE)["tasks"])
    out = run_dir(args.run_id)
    REFS.mkdir(parents=True, exist_ok=True)
    refs = {}
    for task in tasks:
        records = variance.load_samples(out, task, "B")
        rows = [variance.analyze_sample(r) for r in records]
        number = variance.select_reference(rows)
        row = next(r for r in rows if r["sample"] == number)
        record = next(r for r in records if r["sample"] == number)
        (REFS / f"{task}.py").write_text(record["code"], encoding="utf-8")
        refs[task] = {
            "run_id": args.run_id,
            "condition": "B",
            "sample": number,
            "exact_fingerprint": row["exact_fingerprint"],
            "shape_fingerprint": row["shape_fingerprint"],
        }
        print(f"{task}: reference = B sample {number:02d}")
    (REFS / "references.json").write_text(json.dumps(refs, indent=2, sort_keys=True) + "\n")
    return 0


def cmd_report(args) -> int:
    path = run_dir(args.run_id) / "analysis.json"
    if not path.is_file():
        sys.exit(f"{path.relative_to(ROOT)} not found; run `analyze` first")
    print(variance.headline_table(json.loads(path.read_text())), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM output variance experiment")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--run-id", required=True)
    g.add_argument("--conditions", default="A,B")
    g.add_argument("--samples", type=int, default=20)
    g.add_argument("--tasks", default="")
    g.add_argument("--jobs", type=int, default=4)
    g.add_argument("--model", default=variance.DEFAULT_MODEL)
    g.add_argument("--backend", choices=["auto", "api", "cli"], default="auto")
    a = sub.add_parser("analyze")
    a.add_argument("--run-id", required=True)
    a.add_argument("--no-mine", action="store_true")
    r = sub.add_parser("reference")
    r.add_argument("--run-id", required=True)
    p = sub.add_parser("report")
    p.add_argument("--run-id", required=True)
    args = parser.parse_args()
    return {"generate": cmd_generate, "analyze": cmd_analyze,
            "reference": cmd_reference, "report": cmd_report}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
