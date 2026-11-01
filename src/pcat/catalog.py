"""Load, validate and index the catalog on disk (spec sections 5, 8, 9, 10).

Layout: <root>/catalog/<category>/<pattern_id>[@v<N>]/{pattern.yaml,impl.py,test_impl.py}
where <pattern_id> is the id without its category segment and the "@v<N>"
suffix is present only for version N >= 2.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from pcat import canonical
from pcat.errors import CanonicalizationError, CatalogError
from pcat.schema import PatternMeta

CATALOG_DIR = "catalog"
INDEX_FILE = "index.json"
YAML_FILE = "pattern.yaml"
IMPL_FILE = "impl.py"
TEST_FILE = "test_impl.py"
TEST_TIMEOUT_SECONDS = 300

INDEX_FIELDS = (
    "id",
    "version",
    "title",
    "category",
    "variant_of",
    "behavior",
    "status",
    "fingerprint",
    "path",
)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


@dataclass
class Pattern:
    """One pattern folder. `meta` is None when pattern.yaml is invalid."""

    root: Path
    folder: Path
    meta: PatternMeta | None = None
    load_errors: list[str] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return self.folder.relative_to(self.root).as_posix()

    @property
    def label(self) -> str:
        return self.meta.key if self.meta else self.rel

    @property
    def yaml_path(self) -> Path:
        return self.folder / YAML_FILE

    @property
    def impl_path(self) -> Path:
        return self.folder / IMPL_FILE

    @property
    def test_path(self) -> Path:
        return self.folder / TEST_FILE


def find_root(start: Path | None = None) -> Path:
    """Nearest directory at or above `start` that contains a `catalog/` folder."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / CATALOG_DIR).is_dir():
            return candidate
    raise CatalogError(f"no {CATALOG_DIR}/ directory found at or above {start}; use --root")


def folder_for(root: Path, pattern_id: str, version: int = 1) -> Path:
    """Expected folder for `pattern_id` at `version`."""
    category, rest = pattern_id.split(".", 1)
    name = rest if version == 1 else f"{rest}@v{version}"
    return root / CATALOG_DIR / category / name


def discover(root: Path) -> list[Path]:
    base = root / CATALOG_DIR
    if not base.is_dir():
        raise CatalogError(f"{base} is not a directory")
    folders = []
    for category in sorted(base.iterdir()):
        if not category.is_dir() or _ignored(category.name):
            continue
        for folder in sorted(category.iterdir()):
            if folder.is_dir() and not _ignored(folder.name):
                folders.append(folder)
    return folders


def _ignored(name: str) -> bool:
    return name.startswith(".") or name == "__pycache__"


def parse_meta(text: str) -> tuple[PatternMeta | None, list[str]]:
    """Parse pattern.yaml text. Returns (meta, errors)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return None, [f"{YAML_FILE} is not valid YAML: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{YAML_FILE} must be a mapping"]
    try:
        return PatternMeta.model_validate(data), []
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(root)"
            msg = err["msg"].removeprefix("Value error, ")
            errors.append(f"{YAML_FILE}: {loc}: {msg}")
        return None, errors


def load_pattern(root: Path, folder: Path) -> Pattern:
    pattern = Pattern(root=root, folder=folder)
    if not pattern.yaml_path.is_file():
        pattern.load_errors.append(f"missing {YAML_FILE}")
        return pattern
    meta, errors = parse_meta(pattern.yaml_path.read_text(encoding="utf-8"))
    pattern.meta, pattern.load_errors = meta, errors
    if meta is not None:
        expected = folder_for(root, meta.id, meta.version)
        if folder.resolve() != expected.resolve():
            pattern.load_errors.append(
                f"folder does not match id/version: expected "
                f"{expected.relative_to(root).as_posix()}"
            )
    return pattern


def load_catalog(root: Path) -> list[Pattern]:
    return [load_pattern(root, folder) for folder in discover(root)]


def resolve(patterns: list[Pattern], ref: str) -> list[Pattern]:
    """Patterns matching `ref`: "id" (all versions) or "id@vN" (one version)."""
    m = re.fullmatch(r"(.+)@v(\d+)", ref)
    pid, version = (m.group(1), int(m.group(2))) if m else (ref, None)
    found = [
        p
        for p in patterns
        if p.meta and p.meta.id == pid and (version is None or p.meta.version == version)
    ]
    return sorted(found, key=lambda p: p.meta.version)


def get_one(root: Path, ref: str) -> Pattern:
    """The pattern for `ref`; a bare id selects the highest version."""
    patterns = load_catalog(root)
    found = resolve(patterns, ref)
    if not found:
        raise CatalogError(f"unknown pattern {ref!r}")
    return found[-1]


# --------------------------------------------------------------------------- #
# Code, fingerprints, index
# --------------------------------------------------------------------------- #


def analyze_pattern(pattern: Pattern) -> canonical.CanonicalResult:
    if pattern.meta is None:
        raise CatalogError(f"{pattern.rel}: invalid {YAML_FILE}")
    if not pattern.impl_path.is_file():
        raise CatalogError(f"{pattern.label}: missing {IMPL_FILE}")
    source = pattern.impl_path.read_text(encoding="utf-8")
    return canonical.analyze(source, pattern.meta.entry_point, pattern.meta.keep_annotations)


def index_entries(patterns: list[Pattern]) -> list[dict]:
    """Index entries from pattern metadata (stored, approved fingerprints)."""
    bad = [p for p in patterns if p.meta is None]
    if bad:
        raise CatalogError(
            "cannot build index; invalid metadata in: " + ", ".join(p.rel for p in bad)
        )
    entries = []
    for p in patterns:
        meta = p.meta.model_dump()
        entry = {k: meta[k] for k in INDEX_FIELDS if k != "path"}
        entry["path"] = p.rel
        entries.append(entry)
    return sorted(entries, key=lambda e: (e["id"], e["version"]))


def index_text(patterns: list[Pattern]) -> str:
    return json.dumps(index_entries(patterns), sort_keys=True, indent=2) + "\n"


def write_index(root: Path) -> Path:
    path = root / CATALOG_DIR / INDEX_FILE
    _write_text(path, index_text(load_catalog(root)))
    return path


def read_index(root: Path) -> list[dict]:
    path = root / CATALOG_DIR / INDEX_FILE
    if not path.is_file():
        raise CatalogError(f"{path} not found; run `pcat index`")
    return json.loads(path.read_text(encoding="utf-8"))


def write_fingerprint(pattern: Pattern, value: str) -> None:
    """Set `fingerprint:` in pattern.yaml without disturbing other lines."""
    text = pattern.yaml_path.read_text(encoding="utf-8")
    line = f"fingerprint: {value}"
    new, count = re.subn(r"(?m)^fingerprint:.*$", line, text)
    if count == 0:
        new = text.rstrip("\n") + "\n" + line + "\n"
    _write_text(pattern.yaml_path, new)


def _write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# --------------------------------------------------------------------------- #
# Validation (spec section 10)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Problem:
    check: str  # "1".."10", or "immutable" for the optional --base check
    subject: str
    message: str

    def __str__(self) -> str:
        return f"{self.subject}: [check {self.check}] {self.message}"


def run_pattern_tests(folder: Path) -> tuple[bool, str]:
    """Run one pattern's test_impl.py in its own pytest process."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--rootdir={folder}",
        f"--confcutdir={folder}",
        str(folder / TEST_FILE),
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            cmd,
            cwd=folder,
            env=env,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {TEST_TIMEOUT_SECONDS}s"
    output = (proc.stdout + proc.stderr).strip()
    summary = output.splitlines()[-1] if output else ""
    return proc.returncode == 0, summary


def validate(
    root: Path,
    refs: list[str] | None = None,
    run_tests: bool = True,
    base: str | None = None,
) -> list[Problem]:
    """Run all checks. Returns problems (empty list = valid)."""
    patterns = load_catalog(root)
    problems: list[Problem] = []

    if refs:
        selected: list[Pattern] = []
        for ref in refs:
            found = resolve(patterns, ref)
            if not found:
                problems.append(Problem("1", ref, "no such pattern in the catalog"))
            selected.extend(p for p in found if p not in selected)
    else:
        selected = list(patterns)
    selected_labels = {p.label for p in selected}

    computed: dict[str, str] = {}  # label -> computed fingerprint
    for pattern in selected:
        problems.extend(_check_pattern(pattern, computed, run_tests))

    cross = _cross_checks(root, patterns, computed)
    if base:
        cross.extend(_immutability_checks(root, patterns, base))
    if refs:
        cross = [
            p for p in cross if p.check == "10" or set(p.subject.split(" & ")) & selected_labels
        ]
    problems.extend(cross)
    return problems


def _check_pattern(pattern: Pattern, computed: dict[str, str], run_tests: bool) -> list[Problem]:
    label = pattern.label
    out = [Problem("1", label, err) for err in pattern.load_errors]
    if pattern.meta is None:
        return out
    meta = pattern.meta

    # 2 + 3: impl.py structure and entry point
    if not pattern.impl_path.is_file():
        out.append(Problem("2", label, f"missing {IMPL_FILE}"))
        source = None
    else:
        source = pattern.impl_path.read_text(encoding="utf-8")
    result = None
    if source is not None:
        try:
            functions = canonical.list_functions(source)
        except CanonicalizationError as exc:
            out.append(Problem("2", label, f"{IMPL_FILE}: {exc}"))
            functions = None
        if functions is not None:
            if meta.entry_point not in functions:
                out.append(
                    Problem(
                        "3",
                        label,
                        f"entry_point {meta.entry_point!r} not found in {IMPL_FILE} "
                        f"(functions: {', '.join(functions)})",
                    )
                )
            else:
                try:
                    result = canonical.analyze(source, meta.entry_point, meta.keep_annotations)
                except CanonicalizationError as exc:
                    out.append(Problem("2", label, f"{IMPL_FILE}: {exc}"))

    if result is not None:
        computed[label] = result.fingerprint
        # 4: stored fingerprint
        if meta.fingerprint is None:
            out.append(
                Problem("4", label, f"fingerprint not set; run `pcat fingerprint {meta.id} --write`")
            )
        elif meta.fingerprint != result.fingerprint:
            out.append(
                Problem(
                    "4",
                    label,
                    f"fingerprint mismatch: pattern.yaml has {meta.fingerprint[:12]}..., "
                    f"{IMPL_FILE} gives {result.fingerprint[:12]}... Approved patterns are "
                    f"immutable: create version {meta.version + 1} instead of editing",
                )
            )
        # 9: idempotence
        try:
            again = canonical.canonicalize(
                canonical.render(result.text, result.name_map),
                meta.entry_point,
                meta.keep_annotations,
            )
        except Exception as exc:  # noqa: BLE001 - any failure is a check failure
            out.append(Problem("9", label, f"render/canonicalize round trip failed: {exc}"))
        else:
            if again != result.text:
                out.append(Problem("9", label, "canonicalize(render(canonical)) != canonical"))

    # 8: tests
    if not pattern.test_path.is_file():
        out.append(Problem("8", label, f"missing {TEST_FILE}"))
    elif run_tests:
        ok, summary = run_pattern_tests(pattern.folder)
        if not ok:
            out.append(
                Problem(
                    "8",
                    label,
                    f"tests failed ({summary}); run: pytest "
                    f"{pattern.test_path.relative_to(pattern.root).as_posix()}",
                )
            )
    return out


def _cross_checks(root: Path, patterns: list[Pattern], computed: dict[str, str]) -> list[Problem]:
    out: list[Problem] = []
    valid = [p for p in patterns if p.meta is not None]
    active = [p for p in valid if p.meta.status == "active"]

    # 5: duplicate fingerprints among active patterns
    by_fp: dict[str, list[str]] = {}
    for p in active:
        fp = computed.get(p.label) or p.meta.fingerprint
        if fp:
            by_fp.setdefault(fp, []).append(p.label)
    for fp, labels in sorted(by_fp.items()):
        if len(labels) > 1:
            out.append(
                Problem("5", " & ".join(labels), f"active patterns share fingerprint {fp[:12]}...")
            )

    # 6: identical behavior within a variant family (active only)
    families: dict[str, list[Pattern]] = {}
    for p in active:
        if p.meta.variant_of:
            families.setdefault(p.meta.variant_of, []).append(p)
    for family, members in sorted(families.items()):
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                if a.meta.behavior == b.meta.behavior:
                    out.append(
                        Problem(
                            "6",
                            f"{a.label} & {b.label}",
                            f"variants of {family!r} have identical behavior maps; "
                            "variants must differ in behavior",
                        )
                    )

    # 7: replaced_by must resolve to another existing pattern
    for p in valid:
        if p.meta.status != "deprecated":
            continue
        ref = p.meta.replaced_by
        targets = [t for t in resolve(valid, ref) if t is not p]
        if "@v" not in ref:
            targets = [t for t in targets if t.meta.id != p.meta.id or t.meta.version > p.meta.version]
        if not targets:
            out.append(
                Problem("7", p.label, f"replaced_by {ref!r} does not resolve to another pattern")
            )

    # 10: index.json up to date
    index_path = root / CATALOG_DIR / INDEX_FILE
    if len(valid) != len(patterns):
        out.append(Problem("10", INDEX_FILE, "cannot check index while metadata is invalid"))
    else:
        expected = index_text(patterns)
        actual = index_path.read_text(encoding="utf-8") if index_path.is_file() else None
        if actual is None:
            out.append(Problem("10", INDEX_FILE, "missing; run `pcat index`"))
        elif actual != expected:
            out.append(Problem("10", INDEX_FILE, "out of date; run `pcat index` and commit it"))
    return out


# Fields of an approved pattern version that a later change must not touch.
IMMUTABLE_FIELDS = ("id", "version", "behavior", "entry_point", "keep_annotations", "fingerprint")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _immutability_checks(root: Path, patterns: list[Pattern], base: str) -> list[Problem]:
    """Compare against git ref `base`: approved versions must not change or vanish."""
    out: list[Problem] = []
    listing = _git(root, "ls-tree", "-r", "--name-only", base, "--", f"{CATALOG_DIR}/")
    if listing.returncode != 0:
        return [Problem("immutable", base, f"cannot read git ref: {listing.stderr.strip()}")]
    current = {p.rel: p for p in patterns}
    for line in sorted(listing.stdout.splitlines()):
        path = Path(line)
        if path.name != YAML_FILE or len(path.parts) != 4:
            continue
        rel = path.parent.as_posix()
        shown = _git(root, "show", f"{base}:./{line}")
        old_meta, _ = parse_meta(shown.stdout) if shown.returncode == 0 else (None, [])
        if old_meta is None:
            continue
        pattern = current.get(rel)
        if pattern is None or pattern.meta is None:
            out.append(
                Problem("immutable", old_meta.key, f"approved pattern at {rel} was removed or broken")
            )
            continue
        for name in IMMUTABLE_FIELDS:
            if getattr(old_meta, name) != getattr(pattern.meta, name):
                out.append(
                    Problem(
                        "immutable",
                        old_meta.key,
                        f"{name} changed since {base}; approved patterns are immutable, "
                        f"create version {old_meta.version + 1} instead",
                    )
                )
    return out
