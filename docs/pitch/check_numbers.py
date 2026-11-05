"""Check that every number in the pitch is registered in claims.md, and every registered
number is in the section it cites.

    python docs/pitch/check_numbers.py        # exit 1 and a list of problems if any

Reads `one-pager.md`, `faq.md` and `deck.pptx` (slide text, speaker notes and chart data).
In Markdown, code spans, code blocks, link targets and list or heading numbers are
skipped; everywhere, numbers glued to letters or identifiers (`v5.1`, `PC100`, `top-1`,
`#3f9a1c2e`) are names, not numbers. Standard library only.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CHECKED_MD = ["one-pager.md", "faq.md"]
DECK = "deck.pptx"
NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)*(?:/\d[\d,]*(?:\.\d+)?)?%?")
REGISTER_HEADINGS = ("Claims", "Product facts")


def numbers(text: str) -> list[str]:
    """Number tokens in plain text: `12/12`, `$14.59`, `4,031`, `0.75`."""
    out = []
    for m in NUMBER.finditer(text):
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        if before.isalnum() or before in "_@#-." or after.isalpha() or after in "_@#":
            continue
        tok = m.group().rstrip(",.")
        if tok:
            out.append(tok)
    return out


def markdown_text(md: str) -> str:
    """Prose of a Markdown file without code, link targets and list/heading numbers."""
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"`[^`\n]*`", " ", md)
    md = re.sub(r"\]\([^)]*\)", "]", md)
    md = re.sub(r"(?m)^\s*(#+\s*)?\d+\.\s", " ", md)
    return md.replace("**", "")


def sections(md: str) -> dict[str, str]:
    """Heading text -> body until the next heading (any level)."""
    out: dict[str, str] = {}
    current, lines = None, []
    in_code = False
    for line in md.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#+)\s+(.*?)\s*$", line)
        if m:
            if current is not None:
                out.setdefault(current, "\n".join(lines))
            current, lines = m.group(2), []
        else:
            lines.append(line)
    if current is not None:
        out.setdefault(current, "\n".join(lines))
    return out


def register(claims_md: str) -> list[dict]:
    """Rows of the tables under the register headings of claims.md."""
    rows, heading, header = [], None, None
    for line in claims_md.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            heading, header = m.group(1).strip(), None
            continue
        if heading not in REGISTER_HEADINGS or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
        elif not set("".join(cells)) <= set("-: "):
            rows.append(dict(zip(header, cells)))
    return rows


def deck_text(path: Path) -> list[tuple[str, str]]:
    """(part name, text) for every slide, notes page and chart in the deck."""
    out = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            if re.match(r"ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml$", name):
                xml = z.read(name).decode("utf-8")
                xml = re.sub(r"<a:fld [^>]*>.*?</a:fld>", "", xml, flags=re.S)  # slide-number fields
                paras = re.findall(r"<a:p>(.*?)</a:p>", xml, flags=re.S)
                text = "\n".join("".join(re.findall(r"<a:t>([^<]*)</a:t>", p)) for p in paras)
                out.append((name, text))
            elif re.match(r"ppt/charts/chart\d+\.xml$", name):
                xml = z.read(name).decode("utf-8")
                vals = re.findall(r"<c:v>([^<]*)</c:v>", xml)
                out.append((name, "\n".join(vals)))
    return out


def unescape(s: str) -> str:
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace(
        "&amp;", "&")


def check() -> list[str]:
    problems: list[str] = []
    rows = register((HERE / "claims.md").read_text(encoding="utf-8"))
    allowed: set[str] = set()
    for row in rows:
        toks = [t.strip() for t in row.get("Numbers", "").split(";") if t.strip()]
        allowed.update(toks)
        srcs = re.findall(r"`([^`]+)`\s*§\s*([^;]+)", row.get("Source", ""))
        if not srcs:
            problems.append(f"claims.md {row.get('ID')}: no source")
            continue
        found: set[str] = set()
        for file, head in srcs:
            p = REPO / file
            if not p.is_file():
                problems.append(f"claims.md {row.get('ID')}: source file {file} does not exist")
                continue
            secs = sections(p.read_text(encoding="utf-8"))
            if head.strip() not in secs:
                problems.append(f"claims.md {row.get('ID')}: no section '{head.strip()}' in {file}")
                continue
            body = secs[head.strip()].replace("**", "")
            found.update(numbers(head) + numbers(body))
        for t in toks:
            if t not in found:
                problems.append(f"claims.md {row.get('ID')}: {t} is not in the cited section(s)")
    targets: list[tuple[str, str]] = []
    for name in CHECKED_MD:
        targets.append((name, markdown_text((HERE / name).read_text(encoding="utf-8"))))
    deck = HERE / DECK
    if not deck.is_file():
        problems.append(f"{DECK} missing")
    else:
        targets += [(f"{DECK}:{part}", unescape(text)) for part, text in deck_text(deck)]
    for name, text in targets:
        for t in numbers(text):
            if t not in allowed:
                problems.append(f"{name}: {t} is not registered in claims.md")
    return sorted(set(problems))


def main() -> int:
    problems = check()
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
