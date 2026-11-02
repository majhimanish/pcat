"""`pcat` command-line interface (spec section 8).

Every command exits non-zero on failure and prints one error line per problem
to stderr.
"""

from __future__ import annotations

import ast
import functools
import json
import keyword
import re
from pathlib import Path
from typing import List, Optional

import typer
import yaml

from pcat import canonical
from pcat import catalog as cat
from pcat import miner
from pcat.errors import PcatError
from pcat.schema import ID_PATTERN

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    help="Pattern catalog: scaffold, import, validate, index, show and render verified patterns.",
)

_state: dict[str, Optional[Path]] = {"root": None}

DEFAULT_OWNER = "@platform-team"


def _root() -> Path:
    return _state["root"] or cat.find_root()


def _fail(message: str) -> None:
    for line in message.splitlines() or [""]:
        typer.echo(f"error: {line}", err=True)
    raise typer.Exit(1)


def _guard(fn):
    """Turn PcatError into `error: ...` + exit code 1."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PcatError as exc:
            _fail(str(exc))
        except OSError as exc:
            _fail(f"{exc.filename or ''}: {exc.strerror or exc}".lstrip(": "))

    return wrapper


@app.callback()
def main(
    root: Optional[Path] = typer.Option(
        None,
        "--root",
        envvar="PCAT_ROOT",
        help="Repository root containing catalog/ (default: nearest parent that has one).",
    ),
) -> None:
    _state["root"] = root.resolve() if root else None


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #

YAML_TEMPLATE = """\
id: {id}
version: 1
title: {title}
summary: {summary}
category: {category}
variant_of: {variant_of}
behavior:                 # behavior-relevant facts; variants must differ here
{behavior}
entry_point: {entry_point}
owner: "{owner}"
status: active            # active | deprecated
replaced_by: null         # id, required when deprecated
keep_annotations: true
fingerprint: {fingerprint}
"""

IMPL_TEMPLATE = '''\
"""TODO: describe {entry_point}."""


def {entry_point}(value):
    raise NotImplementedError
'''

TEST_TEMPLATE = '''\
from impl import {entry_point}


def test_write_real_tests():
    # Replace with real tests: normal cases, edge cases and empty input.
    raise NotImplementedError("write tests for {entry_point}")
'''


def _check_new_id(root: Path, pattern_id: str) -> Path:
    if not re.fullmatch(ID_PATTERN, pattern_id):
        raise PcatError(
            f"invalid id {pattern_id!r}: use dotted lowercase segments, e.g. search.binary_search.iterative"
        )
    folder = cat.folder_for(root, pattern_id, 1)
    if folder.exists():
        raise PcatError(f"{folder.relative_to(root).as_posix()} already exists")
    return folder


def _title_for(pattern_id: str) -> str:
    parts = pattern_id.split(".")[1:]
    title = parts[0].replace("_", " ").capitalize()
    if len(parts) > 1:
        title += " (" + ", ".join(p.replace("_", " ") for p in parts[1:]) + ")"
    return title


def _variant_of_for(pattern_id: str) -> str:
    parts = pattern_id.split(".")
    return ".".join(parts[:2]) if len(parts) >= 3 else "null"


def _yaml_scalar(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)  # JSON strings are valid YAML scalars


def _write_pattern(folder: Path, files: dict[str, str]) -> None:
    folder.mkdir(parents=True)
    for name, text in files.items():
        cat._write_text(folder / name, text)


def _next_steps(root: Path, folder: Path, pattern_id: str) -> None:
    rel = folder.relative_to(root).as_posix()
    typer.echo(f"created {rel}/")
    typer.echo("next: edit pattern.yaml (summary, behavior) and test_impl.py, then run")
    typer.echo(f"  pcat fingerprint {pattern_id} --write && pcat index && pcat validate {pattern_id}")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


@app.command()
@_guard
def new(pattern_id: str = typer.Argument(..., metavar="ID")) -> None:
    """Scaffold a pattern folder with template pattern.yaml, impl.py and test_impl.py."""
    root = _root()
    folder = _check_new_id(root, pattern_id)
    entry = pattern_id.split(".")[1]
    if keyword.iskeyword(entry):
        entry += "_"
    files = {
        cat.YAML_FILE: YAML_TEMPLATE.format(
            id=pattern_id,
            title=_yaml_scalar(_title_for(pattern_id)),
            summary=_yaml_scalar("TODO: one sentence describing what this pattern does."),
            category=pattern_id.split(".")[0],
            variant_of=_variant_of_for(pattern_id),
            behavior="  todo: describe",
            entry_point=entry,
            owner=DEFAULT_OWNER,
            fingerprint="null         # written by `pcat fingerprint <id> --write`",
        ),
        cat.IMPL_FILE: IMPL_TEMPLATE.format(entry_point=entry),
        cat.TEST_FILE: TEST_TEMPLATE.format(entry_point=entry),
    }
    _write_pattern(folder, files)
    _next_steps(root, folder, pattern_id)


@app.command()
@_guard
def add(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, help="Python file to import from."),
    function: str = typer.Option(..., "--function", help="Name of the top-level function."),
    pattern_id: str = typer.Option(..., "--id", help="New pattern id."),
) -> None:
    """Import a function (and the helpers it calls) from existing code into a new pattern."""
    root = _root()
    folder = _check_new_id(root, pattern_id)
    source = file.read_text(encoding="utf-8")
    impl = canonical.extract_function(source, function)
    result = canonical.analyze(impl, function)

    summary = "TODO: one sentence describing what this pattern does."
    func_node = next(
        n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == function
    )
    doc = ast.get_docstring(func_node)
    if doc and doc.strip():
        summary = doc.strip().splitlines()[0]

    files = {
        cat.YAML_FILE: YAML_TEMPLATE.format(
            id=pattern_id,
            title=_yaml_scalar(_title_for(pattern_id)),
            summary=_yaml_scalar(summary),
            category=pattern_id.split(".")[0],
            variant_of=_variant_of_for(pattern_id),
            behavior="  todo: describe",
            entry_point=function,
            owner=DEFAULT_OWNER,
            fingerprint=result.fingerprint,
        ),
        cat.IMPL_FILE: impl,
        cat.TEST_FILE: TEST_TEMPLATE.format(entry_point=function),
    }
    _write_pattern(folder, files)
    helpers = [f for f in canonical.list_functions(impl) if f != function]
    if helpers:
        typer.echo(f"imported {function} with helpers: {', '.join(helpers)}")
    _next_steps(root, folder, pattern_id)


@app.command("canonical")
@_guard
def canonical_cmd(
    file: Path = typer.Argument(..., exists=True, dir_okay=False),
    entry: Optional[str] = typer.Option(
        None, "--entry", help="Entry-point function (default: first function in the file)."
    ),
    keep_annotations: bool = typer.Option(True, "--keep-annotations/--no-annotations"),
) -> None:
    """Print the canonical form of a Python file."""
    text = canonical.canonicalize(file.read_text(encoding="utf-8"), entry, keep_annotations)
    typer.echo(text, nl=False)


@app.command()
@_guard
def fingerprint(
    pattern_id: str = typer.Argument(..., metavar="ID"),
    write: bool = typer.Option(False, "--write", help="Store the fingerprint in pattern.yaml."),
) -> None:
    """Print a pattern's fingerprint computed from impl.py; --write stores it."""
    pattern = cat.get_one(_root(), pattern_id)
    value = cat.analyze_pattern(pattern).fingerprint
    if write:
        cat.write_fingerprint(pattern, value)
    typer.echo(value)


@app.command()
@_guard
def validate(
    refs: Optional[List[str]] = typer.Argument(None, metavar="[ID]...", help="Default: all patterns."),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Do not run test_impl.py files."),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        help="Git ref of the approved catalog (e.g. origin/main): approved versions must be unchanged.",
    ),
) -> None:
    """Run all catalog checks (spec section 10)."""
    problems = cat.validate(_root(), refs or None, run_tests=not skip_tests, base=base)
    if problems:
        for problem in problems:
            typer.echo(str(problem), err=True)
        typer.echo(f"{len(problems)} problem(s) found", err=True)
        raise typer.Exit(1)
    count = len(cat.load_catalog(_root()))
    typer.echo(f"OK: {count} pattern(s) valid" if not refs else f"OK: {', '.join(refs)} valid")


@app.command()
@_guard
def index() -> None:
    """Regenerate catalog/index.json."""
    path = cat.write_index(_root())
    typer.echo(f"wrote {path.relative_to(_root()).as_posix()}")


@app.command("migrate-fingerprints")
@_guard
def migrate_fingerprints() -> None:
    """Recompute all fingerprints under the current canonicalization rules.

    Rewrites pattern.yaml files whose fingerprint changed, regenerates
    index.json and prints old/new fingerprints. Writes nothing if any pattern
    fails to load or canonicalize.
    """
    rows = cat.migrate_fingerprints(_root())
    width = max([len("id")] + [len(r.key) for r in rows])
    typer.echo(f"{'id':<{width}}  {'old':<64}  {'new':<64}  status")
    for r in rows:
        status = "changed" if r.changed else "unchanged"
        typer.echo(f"{r.key:<{width}}  {(r.old or '-'):<64}  {r.new:<64}  {status}")
    changed = sum(r.changed for r in rows)
    typer.echo(
        f"{changed} of {len(rows)} fingerprint(s) changed; "
        f"rules version {canonical.CANONICAL_VERSION}; wrote {cat.CATALOG_DIR}/{cat.INDEX_FILE}"
    )


@app.command()
@_guard
def show(pattern_id: str = typer.Argument(..., metavar="ID")) -> None:
    """Print metadata and rendered code."""
    pattern = cat.get_one(_root(), pattern_id)
    result = cat.analyze_pattern(pattern)
    typer.echo(yaml.safe_dump(pattern.meta.model_dump(), sort_keys=False, allow_unicode=True), nl=False)
    typer.echo("---")
    typer.echo(canonical.render(result.text, result.name_map), nl=False)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
@_guard
def render(
    ctx: typer.Context,
    pattern_id: str = typer.Argument(..., metavar="ID"),
    names: Optional[List[str]] = typer.Option(
        None, "--names", help="Placeholder renames, e.g. --names f0=find_user v0=users"
    ),
) -> None:
    """Render a pattern with a custom name map (unmapped names keep their real names)."""
    pattern = cat.get_one(_root(), pattern_id)
    result = cat.analyze_pattern(pattern)
    mapping = dict(result.name_map)
    for item in [*(names or []), *ctx.args]:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise PcatError(f"expected key=value in --names, got {item!r}")
        key = key[3:] if key.startswith("f0.") else key
        if key not in mapping:
            raise PcatError(f"unknown placeholder {key!r}; known: {', '.join(mapping)}")
        mapping[key] = value
    rendered = canonical.render(result.text, mapping)
    # A rename that collides with another name would change behaviour; detect
    # it by checking the rendered code still canonicalizes to the same form.
    try:
        same = canonical.canonicalize(rendered, mapping["f0"], pattern.meta.keep_annotations) == result.text
    except PcatError:
        same = False
    if not same:
        raise PcatError("name map makes two names collide (the rendered code would behave differently)")
    typer.echo(rendered, nl=False)


@app.command()
@_guard
def find(file: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Report which catalog pattern matches each top-level function in a file."""
    source = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise PcatError(f"{file}: syntax error at line {exc.lineno}: {exc.msg}") from None
    entries = cat.read_index(_root())["patterns"]
    by_fp: dict[str, list[dict]] = {}
    for entry in entries:
        if entry.get("fingerprint"):
            by_fp.setdefault(entry["fingerprint"], []).append(entry)

    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    if not names:
        raise PcatError(f"{file}: no top-level functions")
    for name in names:
        try:
            snippet = canonical.extract_function(source, name)
            fps = [
                canonical.analyze(snippet, name, keep).fingerprint for keep in (True, False)
            ]
        except PcatError as exc:
            typer.echo(f"{name}: cannot canonicalize: {exc}")
            continue
        matches = []
        for fp in fps:
            for entry in by_fp.get(fp, []):
                label = f"{entry['id']}@v{entry['version']} ({entry['status']})"
                if label not in matches:
                    matches.append(label)
        typer.echo(f"{name}: {', '.join(matches) if matches else 'no match'}")


def _catalog_root_or_none() -> Optional[Path]:
    try:
        return _root()
    except PcatError:
        return None


@app.command()
@_guard
def mine(
    paths: List[Path] = typer.Argument(..., help="Files or directories to mine."),
    out: Path = typer.Option(..., "--out", help="Directory for report.json and report.html."),
    min_nodes: int = typer.Option(20, "--min-nodes", help="Skip functions with fewer AST nodes."),
    min_occurrences: int = typer.Option(3, "--min-occurrences", help="Smallest cluster size."),
    min_fragment_nodes: int = typer.Option(25, "--min-fragment-nodes"),
    include_tests: bool = typer.Option(False, "--include-tests", help="Mine test files too."),
    include_generated: bool = typer.Option(
        False, "--include-generated", help="Mine files marked 'generated by'/'do not edit'."
    ),
    include_trivial: bool = typer.Option(
        False, "--include-trivial", help="Keep functions whose body is one pass/return/raise/..."
    ),
    no_skip_dirs: bool = typer.Option(
        False, "--no-skip-dirs", help="Do not skip .git, venv, build, vendor, migrations, ..."
    ),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", help="Extra glob to skip."),
    no_fragments: bool = typer.Option(False, "--no-fragments", help="Mine whole functions only."),
    jobs: int = typer.Option(1, "--jobs", min=1, help="Worker processes."),
    cache_dir: Path = typer.Option(Path(miner.DEFAULT_CACHE_DIR), "--cache-dir"),
    no_cache: bool = typer.Option(False, "--no-cache"),
) -> None:
    """Find repeated function shapes and fragments; report catalog coverage."""
    settings = miner.MineSettings(
        min_nodes=min_nodes,
        min_occurrences=min_occurrences,
        min_fragment_nodes=min_fragment_nodes,
        include_tests=include_tests,
        include_generated=include_generated,
        include_trivial=include_trivial,
        skip_dirs=not no_skip_dirs,
        excludes=tuple(exclude or ()),
        fragments=not no_fragments,
    )
    result = miner.mine(
        [str(p) for p in paths],
        settings,
        jobs=jobs,
        cache_dir=None if no_cache else str(cache_dir),
        catalog_root=_catalog_root_or_none(),
    )
    json_path, html_path = miner.write_report(result.report, out)
    stats = result.report["stats"]
    cov = result.report["coverage"]
    skipped = ", ".join(f"{k} {v}" for k, v in stats["files_skipped"].items()) or "none"
    typer.echo(f"files: {stats['files_seen']} seen, {stats['files_mined']} mined, skipped: {skipped}")
    typer.echo(
        f"functions: {stats['functions_mined']} mined of {stats['functions_found']} found; "
        f"fragments: {stats['fragments_mined']}"
    )
    typer.echo(
        f"clusters: {stats['function_clusters']} function, {stats['fragment_clusters']} fragment"
    )
    typer.echo(
        f"coverage: {cov['covered']} covered ({cov['covered_percent']}%), "
        f"{cov['near_covered']} near-covered ({cov['near_covered_percent']}%) "
        f"against {cov['catalog_patterns']} catalog pattern(s)"
    )
    typer.echo(f"cache: {result.cache_hits} hit(s), {result.cache_misses} miss(es)")
    typer.echo(f"wrote {json_path} and {html_path}")


if __name__ == "__main__":  # pragma: no cover
    app()
