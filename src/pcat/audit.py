"""`pcat audit`: a one-time, human-reviewed report on existing code (v6).

Finds functions that look derived from a catalog pattern (the opt-in inference variant
from v5.2: similarity >= `lint.INFERRED_GUARD_SIMILARITY`, 0.75) and applies that
pattern's guards. Each finding names the pattern it resembles, the similarity, the margin
to the second-best pattern (shown only: a margin rule is untested), the guard it violates
and a short explanation in the code's own names. It is never a CI gate: findings are
candidates for a person to review, not confirmed bugs. Output is deterministic
(sorted, relative paths, no timestamps).
"""

from __future__ import annotations

import ast
import html
import json
from dataclasses import dataclass, field
from pathlib import Path

from pcat import codeunit, deviation, lint, miner, provenance

NOTE = ("Findings are candidates for human review, not confirmed bugs: each function looks "
        "like a reviewed pattern (similarity >= {t}) and breaks one of that pattern's guards. "
        "Some resemble a pattern without being meant as one; the margin to the second-best "
        "pattern is shown to help judge that. Nothing here fails a build.")


@dataclass
class Finding:
    path: str
    function: str
    line: int
    pattern: str  # key, e.g. auth.password.pbkdf2@v1
    pattern_function: str
    similarity: float
    second_pattern: str | None
    margin: float
    guards: list[dict] = field(default_factory=list)  # {kind, message}

    def to_dict(self) -> dict:
        return {"path": self.path, "function": self.function, "line": self.line, "pattern": self.pattern,
                "pattern_function": self.pattern_function, "similarity": self.similarity,
                "second_pattern": self.second_pattern, "margin": self.margin, "guards": self.guards}


def _guard_kind(message: str) -> str:
    return message.rsplit("[guard ", 1)[-1].rstrip("]") if "[guard " in message else "guard"


def audit(paths: list[str], catalog_root: Path, threshold: float | None = None) -> dict:
    """The audit report as a dict (see `write`)."""
    threshold = lint.INFERRED_GUARD_SIMILARITY if threshold is None else threshold
    catalog = lint.Catalog(Path(catalog_root))
    refs = catalog.refs
    files, _, _ = miner.discover(paths, miner.MineSettings())
    findings: list[Finding] = []
    scanned = matched = marked = 0
    problems: list[str] = []
    for f in files:
        base = Path(paths[f.input_index])
        if lint.in_catalog(Path(f.abs_path), Path(catalog_root), base):
            continue
        shown = f.rel if base.is_dir() else base.name
        if len(paths) > 1:
            shown = f"{base.resolve().name}/{shown}" if base.is_dir() else shown
        try:
            source = Path(f.abs_path).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            problems.append(f"{shown}: cannot parse")
            continue
        module = codeunit.module_for_path(Path(f.abs_path))
        for info in provenance.functions(source, tree):
            scanned += 1
            if info.marker is not None:
                marked += 1  # checked by `pcat lint` already
                continue
            text = provenance.shape_text(info.node)
            if text is None or not refs:
                continue
            ranked = provenance.rank(text, refs)
            sim, best = ranked[0]
            if sim < threshold:
                continue
            matched += 1
            second = next(((s, r) for s, r in ranked if r.pattern_id != best.pattern_id), None)
            pattern = catalog.by_key(best.pattern_id, best.version)
            if pattern is None or not pattern.meta.guards:
                continue
            try:
                analysis = deviation.analyze_function(tree, info.node, pattern, best.function, module=module)
            except Exception as exc:  # noqa: BLE001 - one odd function must not stop an audit
                problems.append(f"{shown}:{info.node.lineno}: cannot analyze {info.qualname}: {exc}")
                continue
            violated = [{"kind": _guard_kind(d.message), "message": d.message}
                        for d in analysis.deviations if d.code == "PC100"]
            if not violated:
                continue
            findings.append(Finding(shown, info.qualname, info.node.lineno, f"{best.pattern_id}@v{best.version}",
                                    best.function, sim, f"{second[1].pattern_id}@v{second[1].version}" if second
                                    else None, round(sim - second[0], 4) if second else round(sim, 4), violated))
    findings.sort(key=lambda x: (x.path, x.line, x.function))
    return {
        "summary": {"files": len(files), "functions_scanned": scanned, "marked_functions_skipped": marked,
                    "functions_resembling_a_pattern": matched, "findings": len(findings),
                    "similarity_threshold": threshold,
                    "catalog_patterns": len({r.pattern_id for r in refs})},
        "note": NOTE.format(t=threshold),
        "findings": [x.to_dict() for x in findings],
        "problems": sorted(problems),
    }


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

CSS = """
body{font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f6f7f9;color:#1d232b}
main{max-width:860px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:.2em 0 .4em}
.note{background:#fff7e0;border-left:4px solid #e0a800;padding:10px 12px;border-radius:6px}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.stat{background:#fff;border-radius:8px;padding:8px 12px;box-shadow:0 1px 2px #0001}
.stat b{display:block;font-size:1.3rem}
.card{background:#fff;border-radius:10px;padding:12px 14px;margin:12px 0;box-shadow:0 1px 3px #0002}
.card h2{font-size:1rem;margin:0 0 4px;word-break:break-word}
.meta{color:#56606d;font-size:.9rem;word-break:break-word}
.guard{margin:8px 0 0;padding:8px 10px;background:#fdecec;border-radius:6px;font-size:.95rem}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em}
@media (prefers-color-scheme:dark){body{background:#14171c;color:#e4e7eb}.stat,.card{background:#1f242b}
.note{background:#3a3115}.guard{background:#3d2224}.meta{color:#9aa4b1}}
"""


def to_html(report: dict) -> str:
    e = html.escape
    s = report["summary"]
    stats = [("Functions scanned", s["functions_scanned"]), ("Resemble a pattern", s["functions_resembling_a_pattern"]),
             ("Findings", s["findings"]), ("Marked (left to pcat lint)", s["marked_functions_skipped"])]
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
           "<title>pcat audit</title><style>" + CSS + "</style></head><body><main>",
           "<h1>pcat audit</h1>", f"<p class=\"note\">{e(report['note'])}</p>", "<div class=\"stats\">"]
    out += [f"<div class=\"stat\"><b>{v}</b>{e(k)}</div>" for k, v in stats]
    out.append("</div>")
    if not report["findings"]:
        out.append("<p>No findings.</p>")
    for f in report["findings"]:
        out.append("<section class=\"card\">")
        out.append(f"<h2><code>{e(f['function'])}</code></h2>")
        out.append(f"<div class=\"meta\"><code>{e(f['path'])}:{f['line']}</code></div>")
        second = f" · second: <code>{e(f['second_pattern'])}</code>" if f["second_pattern"] else ""
        out.append(f"<div class=\"meta\">resembles <code>{e(f['pattern'])}</code> "
                   f"(<code>{e(f['pattern_function'])}</code>), similarity {f['similarity']:.2f}, "
                   f"margin {f['margin']:.2f}{second}</div>")
        for g in f["guards"]:
            out.append(f"<p class=\"guard\">{e(g['message'])}</p>")
        out.append("</section>")
    if report["problems"]:
        out.append("<h2>Skipped</h2><ul>" + "".join(f"<li>{e(p)}</li>" for p in report["problems"]) + "</ul>")
    out.append("</main></body></html>\n")
    return "\n".join(out)


def write(report: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, hp = out_dir / "audit.json", out_dir / "audit.html"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    hp.write_text(to_html(report), encoding="utf-8")
    return jp, hp


def format_summary(report: dict) -> str:
    s = report["summary"]
    lines = [f"scanned {s['functions_scanned']} function(s) in {s['files']} file(s); "
             f"{s['functions_resembling_a_pattern']} resemble a pattern (similarity >= {s['similarity_threshold']}); "
             f"{s['findings']} finding(s)"]
    for f in report["findings"]:
        lines.append(f"  {f['path']}:{f['line']} {f['function']} ~ {f['pattern']} "
                     f"(similarity {f['similarity']:.2f}, margin {f['margin']:.2f}): "
                     + "; ".join(g["kind"] for g in f["guards"]))
    lines.append(report["note"])
    return "\n".join(lines) + "\n"
