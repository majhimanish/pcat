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


def main() -> int:
    parser = argparse.ArgumentParser(description="v5.2 unsafe neighbour")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    vp = sub.add_parser("verify")
    vp.add_argument("--write", action="store_true", help="write experiments/v5.2/verify.json")
    args = parser.parse_args()
    return {"prepare": cmd_prepare, "verify": cmd_verify}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
