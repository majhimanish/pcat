"""Render a miner report (the parsed report.json) as one self-contained HTML file.

The page is built only from report data, makes no external requests (inline
CSS, no scripts, fonts or images) and works at phone width.
"""

from __future__ import annotations

from html import escape

_CSS = """
:root { --bg:#fbfbfa; --fg:#1d1d1b; --muted:#6b6b66; --line:#e2e1dc; --card:#ffffff;
        --accent:#2f5d8a; --code:#f3f2ee; --ok:#2e7d4f; --warn:#9a6a00; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#151614; --fg:#e8e7e2; --muted:#9a9993; --line:#2c2d2a; --card:#1d1e1b;
          --accent:#8db4dc; --code:#232421; --ok:#6fc28f; --warn:#e0b44c; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 1.5rem; margin: 0 0 4px; }
h2 { font-size: 1.15rem; margin: 32px 0 8px; }
.sub { color: var(--muted); margin: 0 0 20px; overflow-wrap: anywhere; }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:10px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
.stat b { display:block; font-size:1.3rem; font-variant-numeric: tabular-nums; }
.stat span { color:var(--muted); font-size:.85rem; }
.rows { border:1px solid var(--line); border-radius:8px; background:var(--card); }
.head, summary { display:grid; gap:8px; align-items:center; padding:8px 12px;
  grid-template-columns: 3rem minmax(9rem,1.4fr) repeat(4, minmax(3.5rem,.6fr)) minmax(6rem,1.2fr); }
.head { color:var(--muted); font-size:.8rem; border-bottom:1px solid var(--line); }
details { border-bottom:1px solid var(--line); }
details:last-child { border-bottom:0; }
summary { cursor:pointer; list-style:none; font-variant-numeric: tabular-nums; }
summary::-webkit-details-marker { display:none; }
summary:hover { background: var(--code); }
.id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.9rem;
      color:var(--accent); overflow-wrap:anywhere; }
.num { text-align:right; }
.match { font-size:.85rem; overflow-wrap:anywhere; }
.match .exact { color: var(--ok); } .match .shape { color: var(--warn); }
.body { padding: 4px 12px 14px; }
pre { background:var(--code); border-radius:6px; padding:10px; overflow-x:auto; margin:8px 0;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }
ul.members { margin: 6px 0 0; padding-left: 1.1rem; font-size:.9rem; }
ul.members li { overflow-wrap:anywhere; }
.muted { color: var(--muted); }
table.cov { border-collapse: collapse; width:100%; font-size:.9rem; }
table.cov td, table.cov th { border-bottom:1px solid var(--line); padding:4px 8px; text-align:left; }
.empty { padding: 12px; color: var(--muted); }
@media (max-width: 640px) {
  .head { display:none; }
  summary { grid-template-columns: 2.2rem 1fr 1fr 1fr; }
  summary .lbl::before { content: attr(data-l) " "; color: var(--muted); font-size:.75rem; }
  summary .id { grid-column: 2 / -1; }
  summary .match { grid-column: 1 / -1; }
  .num { text-align:left; }
}
"""


def _stat(value, label: str) -> str:
    return f'<div class="stat"><b>{escape(str(value))}</b><span>{escape(label)}</span></div>'


def _location(report: dict, member: dict) -> str:
    inputs = report["inputs"]
    base = inputs[member["input"]]["path"] if member["input"] < len(inputs) else "?"
    end = member.get("end_lineno")
    lines = f"{member['lineno']}-{end}" if end and end != member["lineno"] else f"{member['lineno']}"
    return f"{base}/{member['path']}:{lines}"


def _matches(cluster: dict) -> str:
    if not cluster["catalog_matches"]:
        return '<span class="muted">—</span>'
    return ", ".join(
        f'<span class="{escape(m["match"])}">{escape(m["pattern"])} ({escape(m["match"])})</span>'
        for m in cluster["catalog_matches"]
    )


def _cluster_rows(report: dict, clusters: list[dict], kind: str) -> str:
    if not clusters:
        return f'<div class="rows"><div class="empty">No {kind} clusters.</div></div>'
    out = [
        '<div class="rows"><div class="head"><span>#</span><span>cluster</span>'
        '<span class="num">score</span><span class="num">occ.</span><span class="num">nodes</span>'
        '<span class="num">files</span><span>catalog</span></div>'
    ]
    for rank, c in enumerate(clusters, 1):
        members = []
        for m in c["members"]:
            extra = ""
            if m.get("decorators"):
                extra = " " + " ".join("@" + d for d in m["decorators"])
            label = m.get("qualname") or m.get("function", "")
            members.append(
                f"<li><span class=\"id\">{escape(_location(report, m))}</span> "
                f"{escape(label)}<span class=\"muted\">{escape(extra)} "
                f"[#{m['index']}, exact {escape(m['exact_fingerprint'][:12])}]</span></li>"
            )
        groups = ", ".join(
            f"{g['count']}× {escape(g['exact_fingerprint'][:12])}" for g in c["exact_groups"]
        )
        out.append(
            f'<details id="{escape(c["id"])}"><summary>'
            f'<span class="muted">{rank}</span><span class="id">{escape(c["id"])}</span>'
            f'<span class="num lbl" data-l="score">{c["score"]}</span>'
            f'<span class="num lbl" data-l="occ.">{c["occurrences"]}</span>'
            f'<span class="num lbl" data-l="nodes">{c["node_count"]}</span>'
            f'<span class="num lbl" data-l="files">{c["distinct_files"]}</span>'
            f'<span class="match">{_matches(c)}</span></summary>'
            f'<div class="body"><div class="muted">exact sub-groups: {groups}; '
            f'inputs: {c["distinct_inputs"]}</div>'
            f'<pre>{escape(c["shape_text"])}</pre>'
            f'<ul class="members">{"".join(members)}</ul></div></details>'
        )
    out.append("</div>")
    return "".join(out)


def render(report: dict) -> str:
    stats = report["stats"]
    cov = report["coverage"]
    settings = report["settings"]
    inputs = ", ".join(
        i["path"] + (f" @ {i['git']['tag'] or i['git']['commit'][:12]}" if i.get("git") else "")
        for i in report["inputs"]
    )
    skipped_total = sum(stats["files_skipped"].values())
    filtered_total = sum(stats["functions_filtered"].values())
    summary = "".join(
        [
            _stat(stats["files_seen"], "files seen"),
            _stat(stats["files_mined"], "files mined"),
            _stat(skipped_total, "files skipped"),
            _stat(stats["functions_mined"], "functions mined"),
            _stat(filtered_total, "functions filtered"),
            _stat(stats["fragments_mined"], "fragments mined"),
            _stat(stats["function_clusters"], "function clusters"),
            _stat(stats["fragment_clusters"], "fragment clusters"),
            _stat(f"{cov['covered_percent']}%", f"covered ({cov['covered']})"),
            _stat(f"{cov['near_covered_percent']}%", f"near-covered ({cov['near_covered']})"),
        ]
    )
    reasons = "; ".join(
        f"{escape(k)}: {v}" for k, v in [*stats["files_skipped"].items(), *stats["functions_filtered"].items()]
    )
    cov_rows = "".join(
        f"<tr><td class=\"id\">{escape(p['pattern'])}</td><td>{p['covered']}</td>"
        f"<td>{p['near_covered']}</td></tr>"
        for p in cov["patterns"]
    )
    cov_table = (
        f'<table class="cov"><tr><th>pattern</th><th>covered</th><th>near-covered</th></tr>'
        f"{cov_rows}</table>"
        if cov_rows
        else '<p class="muted">No catalog patterns were available for coverage.</p>'
    )
    skipped = "".join(
        f"<li><span class=\"id\">{escape(report['inputs'][s['input']]['path'])}/{escape(s['path'])}</span>"
        f" {escape(s['reason'])}{': ' + escape(s['error']) if s.get('error') else ''}</li>"
        for s in report["skipped_files"]
        if s["reason"] == "parse_error"
    )
    settings_text = ", ".join(f"{k}={v}" for k, v in sorted(settings.items()))
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>Pattern mining report</title><style>{_CSS}</style></head><body><main>"
        "<h1>Pattern mining report</h1>"
        f'<p class="sub">{escape(inputs)} · canonical v{report["canonical_version"]} · '
        f'shape v{report["shape_version"]}</p>'
        f'<div class="grid">{summary}</div>'
        f'<p class="sub" style="margin-top:10px">{reasons}</p>'
        f'<p class="sub">settings: {escape(settings_text)}</p>'
        f"<h2>Catalog coverage</h2>{cov_table}"
        f"<h2>Function clusters ({len(report['function_clusters'])})</h2>"
        f"{_cluster_rows(report, report['function_clusters'], 'function')}"
        f"<h2>Fragment clusters ({len(report['fragment_clusters'])})</h2>"
        f"{_cluster_rows(report, report['fragment_clusters'], 'fragment')}"
        + (f"<h2>Unparseable files</h2><ul class=\"members\">{skipped}</ul>" if skipped else "")
        + "</main></body></html>\n"
    )
