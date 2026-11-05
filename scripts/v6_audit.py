"""v6 Part C: run `pcat audit` on the three v5 apps and on the planted v5.2 working copies.

    python scripts/v6_audit.py

A measurement, not tuning: the threshold is the v5.2 opt-in variant (0.75), unchanged.
Outputs: experiments/v6/audit/<app>/audit.{json,html} and planted.json.
"""

from __future__ import annotations

import _labpath  # noqa: F401  (experiments/lib on sys.path)

import json
import shutil
import sys
import tempfile
from pathlib import Path

from pcat import audit
from pcatlab import v52

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "v6" / "audit"
APPS = ROOT / ".bench" / "apps"
CATALOGS = ROOT / "experiments" / "v5" / "catalogs"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    totals = {}
    for app in ("ctfd", "healthchecks", "lnbits"):
        report = audit.audit([str(APPS / app)], CATALOGS / app)
        audit.write(report, OUT / app)
        totals[app] = report["summary"]
        print(f"{app}: {report['summary']}")
    rows = []
    with tempfile.TemporaryDirectory(prefix="pcat-v6-audit-") as tmp:
        for task in v52.load_tasks(ROOT / "experiments" / "v5.2" / "tasks.yaml"):
            dest = Path(tmp) / task.id
            v52.prepare_workdir(APPS / task.app, dest, task, "baseline", v52.neighbour_code(ROOT, task))
            report = audit.audit([str(dest / task.file)], CATALOGS / task.app)
            hit = next((f for f in report["findings"] if f["function"] == task.neighbour.function), None)
            rows.append({"app": task.app, "task": task.id, "neighbour": task.neighbour.function,
                         "intended_guards": list(task.neighbour.violates), "surfaced": hit is not None,
                         "pattern": hit["pattern"] if hit else None,
                         "similarity": hit["similarity"] if hit else None, "margin": hit["margin"] if hit else None,
                         "guards": [g["kind"] for g in hit["guards"]] if hit else [],
                         "other_findings_in_file": sorted(f["function"] for f in report["findings"]
                                                          if f["function"] != task.neighbour.function)})
            shutil.rmtree(dest, ignore_errors=True)
    surfaced = sum(r["surfaced"] for r in rows)
    write_json(OUT / "planted.json", {"note": "pcat audit on the task file of each v5.2 working copy (target "
                                              "removed, neighbour planted)", "surfaced": surfaced,
                                      "planted": len(rows), "rows": rows, "apps": totals})
    print(f"planted neighbours surfaced: {surfaced}/{len(rows)}")
    for r in rows:
        print(f"  {r['task']}: {'yes' if r['surfaced'] else 'no '} {r['similarity']} {r['guards']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
