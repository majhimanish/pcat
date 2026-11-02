"""Benchmark the miner on pinned open-source repositories (spec v2, Part D).

Shallow-clones each repository at a pinned release tag into .bench/repos/,
runs `pcat mine` on all of them together (cold cache) and writes the report to
.bench/report/. Not part of pytest or CI; needs network access and git.

    python scripts/benchmark.py [--jobs N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / ".bench"
REPOS = [
    ("requests", "https://github.com/psf/requests", "v2.32.3"),
    ("flask", "https://github.com/pallets/flask", "3.0.3"),
    ("fastapi", "https://github.com/fastapi/fastapi", "0.115.0"),
]


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def _version(tag: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", tag))


def resolve_tag(url: str, wanted: str) -> str:
    """`wanted` if it exists, else the closest release tag (by version distance)."""
    out = run(["git", "ls-remote", "--tags", "--refs", url]).stdout
    tags = [line.split("refs/tags/", 1)[1] for line in out.splitlines() if "refs/tags/" in line]
    if wanted in tags:
        return wanted
    releases = [t for t in tags if re.fullmatch(r"v?\d+(\.\d+)*", t)]
    target = _version(wanted)
    return min(releases, key=lambda t: (abs(len(_version(t)) - len(target)),
                                        [abs(a - b) for a, b in zip(_version(t), target)]))


def clone(name: str, url: str, wanted: str) -> dict:
    tag = resolve_tag(url, wanted)
    dest = BENCH / "repos" / name
    if dest.exists():
        current = subprocess.run(
            ["git", "-C", str(dest), "describe", "--tags", "--exact-match"],
            capture_output=True, text=True,
        ).stdout.strip()
        if current != tag:
            shutil.rmtree(dest)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "--depth", "1", "--branch", tag, url, str(dest)])
    commit = run(["git", "-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
    return {"name": name, "url": url, "wanted": wanted, "tag": tag, "commit": commit, "path": dest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()

    repos = [clone(*spec) for spec in REPOS]
    for r in repos:
        note = "" if r["tag"] == r["wanted"] else f" (wanted {r['wanted']})"
        print(f"{r['name']}: {r['tag']}{note} {r['commit'][:12]}")

    cache = BENCH / "cache"
    shutil.rmtree(cache, ignore_errors=True)  # cold run: time the real work
    paths = [str(r["path"].relative_to(ROOT)) for r in repos]
    # 1. The spec run: all repos together, default settings.
    # 2. Library code only: FastAPI's docs_src/ tutorial copies dominate run 1,
    #    so also mine without them, down to pairs, to see what real code repeats.
    runs = [
        ("report", []),
        ("report-library", ["--exclude", "docs_src/*", "--min-occurrences", "2"]),
    ]
    timings = {}
    for name, extra in runs:
        out = BENCH / name
        cmd = [
            sys.executable, "-m", "pcat.cli", "--root", str(ROOT), "mine", *paths,
            "--out", str(out), "--jobs", str(args.jobs), "--cache-dir", str(cache), *extra,
        ]
        start = time.perf_counter()
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        timings[name] = round(time.perf_counter() - start, 1)
        print(f"== {name} {' '.join(extra)}")
        print(result.stdout, end="")
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode
        print(f"elapsed: {timings[name]}s with --jobs {args.jobs}")
    meta = {
        "elapsed_seconds": timings,
        "jobs": args.jobs,
        "python": sys.version.split()[0],
        "repos": [{k: v for k, v in r.items() if k != "path"} for r in repos],
    }
    (BENCH / "report" / "benchmark.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
