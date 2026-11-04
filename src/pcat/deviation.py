"""Explainable deviations of a function from the pattern it derives from (v4 Part C).

Standard library only. Both sides are *units* (`codeunit.py`): the function, the
same-file helpers it calls, the constants it reads and the imports it uses.
Deviations are computed as set and structure differences on normalized code
(locals anonymous, imports resolved to their origin, annotations and docstrings
removed), so renaming alone never produces a deviation. Each deviation has a
stable code, a severity, a one-line message in the user's names and a line in
the user's file. A unified diff of the pattern (rendered in the user's names)
against the user's code is attached for display.

Codes (default severity): PC100 guard violated (high), PC101 exception removed
or narrowed (high), PC102 raise/validation removed (high), PC103 library swapped
(high; v5.1: medium when the same check raises a different exception), PC104 broad except added (medium), PC105 call removed (medium), PC106
private access added (medium), PC107 signature changed (medium), PC108 call
added (low), PC109 literal changed (low), PC110 other structural change (low).
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import difflib
import sys
from dataclasses import asdict, dataclass, field

from pcat import canonical, codeunit, guards, requirements, shape
from pcat.codeunit import Unit, name_key

SEVERITY = {
    "PC100": "high", "PC101": "high", "PC102": "high", "PC103": "high",
    "PC104": "medium", "PC105": "medium", "PC106": "medium", "PC107": "medium",
    "PC108": "low", "PC109": "low", "PC110": "low", "PC111": "high",
}
TITLES = {
    "PC100": "guard violated",
    "PC101": "exception removed or narrowed",
    "PC102": "raise or validation removed",
    "PC103": "library swapped",
    "PC104": "broad except added",
    "PC105": "call removed",
    "PC106": "private access added",
    "PC107": "signature changed",
    "PC108": "call added",
    "PC109": "literal changed",
    "PC110": "other structural change",
    "PC111": "marker removed from derived code",
}
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
MAX_DIFF_LINES = 80
LITERAL_REPORT_RATIO = 0.8  # report in-statement literal changes only for closely matching functions


@dataclass(frozen=True)
class Deviation:
    code: str
    severity: str
    message: str
    line: int
    function: str  # the user's function the deviation is in

    def to_dict(self) -> dict:
        return {**asdict(self), "title": TITLES[self.code]}


@dataclass
class Analysis:
    pattern: str  # pattern key, e.g. http.get_with_retry.requests@v1
    pattern_function: str
    function: str  # the user's function
    line: int
    deviations: list[Deviation]
    diff: str
    shape_match: bool
    guards_checked: int = 0
    resolution: str = "full"  # v5.1: "partial" when the code uses names nothing binds
    unknown_names: list[str] = field(default_factory=list)  # those names
    assumed: dict[str, str] = field(default_factory=dict)  # unknown name -> pattern origin assumed
    skipped: list[str] = field(default_factory=list)  # rules not checked because of unknown names

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern, "pattern_function": self.pattern_function,
            "function": self.function, "line": self.line, "shape_match": self.shape_match,
            "guards_checked": self.guards_checked,
            "deviations": [d.to_dict() for d in self.deviations], "diff": self.diff,
            "resolution": self.resolution, "unknown_names": self.unknown_names,
            "assumed": self.assumed, "skipped_rules": self.skipped,
        }


# --------------------------------------------------------------------------- #
# Alignment between the pattern unit and the user's unit
# --------------------------------------------------------------------------- #


@dataclass
class Alignment:
    functions: list[tuple[ast.FunctionDef, ast.FunctionDef]]  # (pattern, user)
    removed_helpers: list[ast.FunctionDef]
    added_helpers: list[ast.FunctionDef]
    params: dict[str, str]  # pattern param of the entry -> user param
    constants: dict[str, str]  # pattern constant -> user constant
    names: dict[int, dict[str, str]] = field(default_factory=dict)  # id(pattern func) -> name map
    global_names: dict[str, str] = field(default_factory=dict)  # functions + constants

    def rename_map(self, pattern_func: ast.FunctionDef) -> dict[str, str]:
        return {**self.global_names, **self.names.get(id(pattern_func), {})}


def _params(func: ast.FunctionDef) -> list[ast.arg]:
    return canonical._arg_nodes(func.args)


def _align_params(p: ast.FunctionDef, u: ast.FunctionDef) -> dict[str, str]:
    pnames = [a.arg for a in _params(p)]
    unames = [a.arg for a in _params(u)]
    out = {n: n for n in pnames if n in unames}
    rest_p = [n for n in pnames if n not in out]
    rest_u = [n for n in unames if n not in out.values()]
    for a, b in zip(rest_p, rest_u):
        if pnames.index(a) == unames.index(b):  # same position: renamed
            out[a] = b
    return out


def _align_constants(pu: Unit, uu: Unit) -> dict[str, str]:
    out = {n: n for n in pu.constants if n in uu.constants}
    rest_u = [n for n in uu.constants if n not in out.values()]
    for name, value in pu.constants.items():
        if name in out:
            continue
        for cand in rest_u:
            if type(uu.constants[cand]) is type(value) and cand not in out.values():
                out[name] = cand
                break
    return out


def _local_map(p: ast.FunctionDef, u: ast.FunctionDef, params: dict[str, str]) -> dict[str, str]:
    pl = canonical._number_locals(p, codeunit.local_names(p))
    ul = canonical._number_locals(u, codeunit.local_names(u))
    inv = {v: k for k, v in ul.items()}
    out = {name: inv[ph] for name, ph in pl.items() if ph in inv}
    out.update(params)
    return out


def align(pu: Unit, uu: Unit) -> Alignment:
    pairs = [(pu.func, uu.func)]
    u_helpers = list(uu.helpers)
    removed, matched_u = [], set()
    by_name = {h.name: h for h in u_helpers}
    for ph in pu.helpers:
        uh = by_name.get(ph.name)
        if uh is not None:
            pairs.append((ph, uh))
            matched_u.add(id(uh))
    remaining_u = [h for h in u_helpers if id(h) not in matched_u]
    for ph in pu.helpers:
        if any(p is ph for p, _ in pairs):
            continue
        if ph.name in uu.undefined_calls:
            continue  # called but defined elsewhere: assume it is the pattern's helper
        if remaining_u:
            uh = remaining_u.pop(0)
            pairs.append((ph, uh))
        else:
            removed.append(ph)
    added = remaining_u
    params = _align_params(pu.func, uu.func)
    constants = _align_constants(pu, uu)
    al = Alignment(pairs, removed, added, params, constants)
    al.global_names = {p.name: u.name for p, u in pairs}
    al.global_names.update(constants)
    for origin_binding, origin in sorted(pu.imports.items()):
        same = sorted(b for b, o in uu.imports.items() if o == origin)
        if same and origin_binding not in same:
            al.global_names[origin_binding] = same[0]
    for p, u in pairs:
        pe, ue = entries(p, pu), entries(u, uu)
        params_map = _align_params(p, u)
        if [e.shape for e in pe] == [e.shape for e in ue]:
            al.names[id(p)] = _local_map(p, u, params_map)
            continue
        mapping = dict(params_map)
        p_locals, u_locals = codeunit.local_names(p), codeunit.local_names(u)
        matcher = difflib.SequenceMatcher(None, [e.shape for e in pe], [e.shape for e in ue], autojunk=False)
        for a, b, size in matcher.get_matching_blocks():
            for ea, eb in zip(pe[a:a + size], ue[b:b + size]):
                for na, nb in zip(_names_in(ea.parts), _names_in(eb.parts)):
                    if na in p_locals and nb in u_locals and na not in mapping \
                            and nb not in mapping.values():
                        mapping[na] = nb
        al.names[id(p)] = mapping
    return al


def _names_in(parts: list) -> list[str]:
    out = []
    for part in parts:
        if part is None:
            continue
        for n in ast.walk(part):
            if isinstance(n, ast.Name):
                out.append(n.id)
            elif isinstance(n, ast.arg):
                out.append(n.arg)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                out.append(n.name)
    return out


class _Renamer(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def visit_Name(self, node: ast.Name):  # noqa: N802
        node.id = self.mapping.get(node.id, node.id)
        return node

    def visit_arg(self, node: ast.arg):  # noqa: N802
        node.arg = self.mapping.get(node.arg, node.arg)
        return node

    def visit_FunctionDef(self, node):  # noqa: N802
        node.name = self.mapping.get(node.name, node.name)
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def in_user_names(node: ast.AST, mapping: dict[str, str]) -> str:
    clone = _strip_docstrings(copy.deepcopy(node))
    return ast.unparse(_Renamer(mapping).visit(clone))


def _strip_docstrings(node: ast.AST) -> ast.AST:
    for n in ast.walk(node):
        if isinstance(n, codeunit.FUNC_TYPES):
            while n.body and canonical._is_string_expr(n.body[0]):
                n.body.pop(0)
            if not n.body:
                n.body.append(ast.Pass())
    return node


def user_spelling(dotted: str, unit: Unit) -> str:
    """`requests.ConnectionError` as the user would write it (`rq.ConnectionError` after
    `import requests as rq`, `KeyChecker` for a class defined in the user's file);
    unchanged when the user has no matching import."""
    spelled = unit.spell(dotted)
    if spelled != dotted:
        return spelled
    best = None
    for binding, origin in unit.imports.items():
        if dotted == origin or dotted.startswith(origin + "."):
            if best is None or len(origin) > len(best[1]) or (len(origin) == len(best[1]) and binding < best[0]):
                best = (binding, origin)
    return dotted if best is None else best[0] + dotted[len(best[1]):]


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


# --------------------------------------------------------------------------- #
# Statement entries (for structure and literal comparison)
# --------------------------------------------------------------------------- #


@dataclass
class Entry:
    shape: str  # literals blanked
    exact: str
    node: ast.AST
    text: str  # as written (original names)
    parts: list = field(default_factory=list)  # the expressions/statement the key was made from


def _key(node: ast.AST, unit: Unit, func: ast.FunctionDef) -> tuple[str, str]:
    anon = codeunit.anonymize(node, unit, func)
    exact = ast.unparse(anon)
    blanked = shape.blank_literals(copy.deepcopy(anon))
    return ast.unparse(blanked), exact


def _expr_text(node, unit, func) -> tuple[str, str]:
    if node is None:
        return "", ""
    return _key(node, unit, func)


def entries(func: ast.FunctionDef, unit: Unit) -> list[Entry]:
    out: list[Entry] = []

    def add(header: str, parts: list[ast.AST | None], node: ast.AST, depth: int, text: str) -> None:
        shapes, exacts = zip(*[_expr_text(p, unit, func) for p in parts]) if parts else ((), ())
        prefix = "  " * depth
        out.append(Entry(prefix + header.format(*shapes), prefix + header.format(*exacts), node, text,
                         list(parts)))

    def walk(body: list[ast.stmt], depth: int, docstrings: bool = False) -> None:
        if docstrings:
            body = [s for i, s in enumerate(body) if not (i == 0 and canonical._is_string_expr(s))]
        for stmt in body:
            visit(stmt, depth)

    def visit(stmt: ast.stmt, depth: int, elif_: bool = False) -> None:
        src = _first_line(stmt)
        if isinstance(stmt, ast.If):
            add(("elif {}:" if elif_ else "if {}:"), [stmt.test], stmt, depth, src)
            walk(stmt.body, depth + 1)
            if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                visit(stmt.orelse[0], depth, elif_=True)
            elif stmt.orelse:
                add("else:", [], stmt, depth, "else:")
                walk(stmt.orelse, depth + 1)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            add("for {} in {}:", [stmt.target, stmt.iter], stmt, depth, src)
            walk(stmt.body, depth + 1)
            if stmt.orelse:
                add("for-else:", [], stmt, depth, "else:")
                walk(stmt.orelse, depth + 1)
        elif isinstance(stmt, ast.While):
            add("while {}:", [stmt.test], stmt, depth, src)
            walk(stmt.body, depth + 1)
            if stmt.orelse:
                add("while-else:", [], stmt, depth, "else:")
                walk(stmt.orelse, depth + 1)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            items = ast.Tuple(elts=[i.context_expr for i in stmt.items], ctx=ast.Load())
            add("with {}:", [items], stmt, depth, src)
            walk(stmt.body, depth + 1)
        elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            add("try:", [], stmt, depth, "try:")
            walk(stmt.body, depth + 1)
            for h in stmt.handlers:
                add("except {}:", [h.type], h, depth, _first_line(h))
                walk(h.body, depth + 1)
            if stmt.orelse:
                add("try-else:", [], stmt, depth, "else:")
                walk(stmt.orelse, depth + 1)
            if stmt.finalbody:
                add("finally:", [], stmt, depth, "finally:")
                walk(stmt.finalbody, depth + 1)
        elif isinstance(stmt, codeunit.FUNC_TYPES):
            add("def {}:", [stmt.args], stmt, depth, src)
            walk(stmt.body, depth + 1, docstrings=True)
        elif isinstance(stmt, ast.Match):
            add("match {}:", [stmt.subject], stmt, depth, src)
            for case in stmt.cases:
                add("case {} if {}:", [case.pattern, case.guard], case, depth + 1, "case ...:")
                walk(case.body, depth + 2)
        else:
            shp, exact = _key(stmt, unit, func)
            prefix = "  " * depth
            out.append(Entry(prefix + shp, prefix + exact, stmt, src, [stmt]))

    walk(func.body, 0, docstrings=True)
    return out


def _first_line(node: ast.AST) -> str:
    try:
        return ast.unparse(node).splitlines()[0]
    except Exception:  # noqa: BLE001
        return type(node).__name__


def _literals(node: ast.AST) -> list:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant)]


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def _runtime_roots(unit: Unit) -> set[str]:
    roots = set()
    origins = set(unit.imports.values()) | {unit.bound[n] for n in unit.bound_imports}
    if unit.module:  # the file's own definitions belong to its package
        origins |= {unit.qualify(n) for n in unit.file_defs}
    for f in unit.functions:
        anon = codeunit.anonymize(f, unit, f)
        for n in ast.walk(anon):
            if isinstance(n, ast.Name) and n.id in origins:
                if not n.id.startswith("."):
                    roots.add(n.id.split(".")[0])
    return roots


def _required_roots(meta) -> set[str]:
    """Import roots of the pattern's `requires` (v5.1: through `import_names`)."""
    return set(requirements.required_roots(meta.requires, getattr(meta, "import_names", None) or {}))


def _parents(func: ast.FunctionDef) -> dict[int, ast.AST]:
    out = {}
    for node in ast.walk(func):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


def _raise_records(unit: Unit) -> list[dict]:
    out = []
    parents = {}
    for f in unit.functions:
        parents.update(_parents(f))
    for node, kind, f in codeunit.raises(unit):
        parent = parents.get(id(node))
        cond = None
        if isinstance(parent, ast.If) and any(s is node for s in parent.body):
            cond = _key(parent.test, unit, f)[0]
        out.append({"node": node, "kind": name_key(kind), "display": unit.spell(kind), "cond": cond,
                    "dotted": kind,
                    "if": parent if cond is not None else None, "func": f})
    return out


def _private_names(unit: Unit) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    for f in unit.functions:
        locals_ = unit.locals_of(f)
        for n in ast.walk(f):
            name = None
            if isinstance(n, ast.Attribute):
                name = n.attr
                shown = f".{n.attr}"
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id in locals_ or n.id in unit.file_names and n.id not in unit.imports:
                    continue
                name = unit.imports.get(n.id, n.id).split(".")[-1]
                shown = unit.imports.get(n.id, n.id)
            if name and name.startswith("_") and not canonical._is_dunder(name):
                out.setdefault(shown, (n.lineno, f.name))
    return out


def _default_key(func: ast.FunctionDef, unit: Unit) -> dict[str, tuple[str, str, str]]:
    """param -> (kind, default shape, default exact)."""
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    out = {}
    pos_defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for a, d in zip(positional, pos_defaults):
        kind = "positional-only" if a in args.posonlyargs else "positional"
        out[a.arg] = (kind, *_expr_text(d, unit, func))
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        out[a.arg] = ("keyword-only", *_expr_text(d, unit, func))
    if args.vararg:
        out["*" + args.vararg.arg] = ("*args", "", "")
    if args.kwarg:
        out["**" + args.kwarg.arg] = ("**kwargs", "", "")
    return out


def _origins(unit: Unit) -> dict[str, str]:
    """name -> resolution for every module-level name the unit refers to by a binding
    it knows (imports and same-file definitions)."""
    out = {name: unit.global_name(name) for name in unit.file_defs | set(unit.imports)}
    return {k: v for k, v in out.items() if k not in unit.unknown}


def _loose(unit: Unit) -> set[str]:
    """Names whose resolution is a guess: unknown names, and same-file definitions
    when the file's module path is unknown (they resolve to a bare name)."""
    used = set()
    for f in unit.functions:
        used |= codeunit._referenced_names(f) - unit.locals_of(f)
    loose = set(unit.unknown)
    if unit.module is None:
        loose |= (unit.file_defs - unit.helper_names - {unit.func.name}) & used
    return loose


def _assume(loose: set[str], unit: Unit, other: Unit) -> dict[str, str]:
    """For each loose name of `unit`, what `other` means by it: the same name bound in
    `other`, else the only origin in `other` whose last segment is that name."""
    origins = _origins(other)
    by_last: dict[str, set[str]] = {}
    for origin in origins.values():
        by_last.setdefault(codeunit.last_segment(origin), set()).add(origin)
    out = {}
    for name in sorted(loose):
        if name in origins:
            out[name] = origins[name]
        elif len(by_last.get(name, ())) == 1:
            target = next(iter(by_last[name]))
            if target != name:
                out[name] = target
    return out


def bind(pu: Unit, uu: Unit) -> tuple[Unit, Unit, dict[str, str]]:
    """Resolve both units through one symbol table (v5.1 Part A).

    - Helpers one side defines and the other imports (or calls, defined elsewhere)
      are compared as the imported name, not as helpers.
    - Loose names on either side (unknown names; same-file definitions of a file
      whose module path is unknown) are assumed to be what the other side means by
      that name. Returns (pattern unit, user unit, assumptions on the user side)."""
    external = [h for h in pu.helpers if h.name not in uu.helper_names
                and (h.name in uu.undefined_calls or h.name in uu.imports)]
    if external:  # helpers the user calls but defines elsewhere: compare without them
        pu = dataclasses.replace(pu, helpers=[h for h in pu.helpers if h not in external], _locals={})
    p_origins = _origins(pu)
    imported = [h for h in uu.helpers if h.name not in pu.helper_names and h.name in p_origins
                and (uu.module is None or name_key(p_origins[h.name]) == name_key(uu.qualify(h.name)))]
    if imported:  # the pattern imports what the user's file defines: compare as that name
        uu = dataclasses.replace(uu, helpers=[h for h in uu.helpers if h not in imported], _locals={})
    p_bound = _assume(_loose(pu), pu, uu)
    u_bound = _assume(_loose(uu), uu, pu)
    if p_bound:
        pu = dataclasses.replace(pu, bound={**pu.bound, **p_bound}, bound_imports=pu.bound_imports | {
            n for n, o in p_bound.items() if o in set(uu.imports.values())})
    if u_bound:
        uu = dataclasses.replace(uu, bound={**uu.bound, **u_bound}, bound_imports=uu.bound_imports | {
            n for n, o in u_bound.items() if o in set(pu.imports.values())})
    return pu, uu, {k: v for k, v in u_bound.items() if k in uu.unknown}


def analyze(pattern_unit: Unit, user_unit: Unit, *, pattern_key: str, pattern_function: str,
            meta=None) -> Analysis:
    """Deviations of `user_unit` from `pattern_unit` (meta: PatternMeta for guards/requires)."""
    pu, uu, assumed = bind(pattern_unit, user_unit)
    skipped: list[str] = []
    al = align(pu, uu)
    devs: list[Deviation] = []
    uname = uu.func.name
    attributed_p: set[int] = set()  # pattern nodes explained by a specific deviation
    attributed_u: set[int] = set()
    attributed_lines: set[int] = set()  # user lines explained by a specific deviation

    def emit(code: str, message: str, line: int, func: str | None = None, severity: str | None = None) -> None:
        devs.append(Deviation(code, severity or SEVERITY[code], message, line, func or uname))

    # PC100: guards -------------------------------------------------------
    suppressed: dict[str, set[str]] = {k: set() for k in ("catch", "call", "nocall", "import", "value")}
    guard_results: list[guards.GuardResult] = []
    if meta is not None:
        selected = guards.applicable(meta, pattern_function)
        names = {**al.constants, **al.params}
        guard_results = guards.check(uu, selected, names)
        for r in guard_results:
            if r.kind in ("min_value", "max_value", "must_include"):
                suppressed["value"].add(r.item)
            if r.skipped:
                skipped.append(f"PC100 guard {r.kind} `{r.item}`")
                suppressed["call" if r.kind == "must_call" else "catch"].update(
                    name_key(i) for i in r.item.split(" | "))
                continue
            if r.ok:
                continue
            emit("PC100", f"{r.message} [guard {r.kind}]", r.line)
            if r.kind == "must_catch":
                attributed_lines.add(r.line)
            if r.kind == "must_catch":
                suppressed["catch"].update(name_key(i) for i in r.item.split(" | "))
            elif r.kind == "must_call":
                suppressed["call"].update(name_key(i) for i in r.item.split(" | "))
            elif r.kind == "must_not_call":
                suppressed["nocall"].add(name_key(r.item))
            elif r.kind == "must_not_import":
                suppressed["import"].add(r.item.split(".")[0])

    # PC103: library swapped ----------------------------------------------
    p_roots, u_roots = _runtime_roots(pu), _runtime_roots(uu)
    # v5.1: a swap is dropping a required library the pattern actually uses at run time
    required = (_required_roots(meta) & p_roots) if meta is not None else set()
    missing_required = sorted(required - u_roots)
    dropped = sorted(p_roots - u_roots - required)
    if uu.unresolved and (missing_required or dropped):  # may be among the unknown names
        skipped.append("PC103 " + ", ".join(f"`{r}`" for r in sorted(set(missing_required) | set(dropped)))
                       + " not seen (imports missing)")
        missing_required, dropped = [], []
    added_third = sorted(r for r in u_roots - p_roots
                         if r not in sys.stdlib_module_names and r not in suppressed["import"])
    added_std = sorted(r for r in u_roots - p_roots if r in sys.stdlib_module_names)
    names = lambda roots: ", ".join(f"`{r}`" for r in roots)  # noqa: E731
    if missing_required:  # a library the pattern requires is dropped or replaced: high
        emit("PC103", f"`{uname}` no longer uses {names(missing_required)}, which the pattern requires "
             f"({', '.join(meta.requires)})" + (f"; it uses {names(added_third)} instead" if added_third else ""),
             uu.func.lineno)
    elif added_third:  # a new third-party library: medium
        emit("PC103", f"`{uname}` adds the third-party {names(added_third)}"
             + (f" and no longer uses {names(dropped)}" if dropped else ""), uu.func.lineno, severity="medium")
    elif dropped or added_std:  # only standard-library or not-required modules differ: low
        std = [r for r in dropped if r in sys.stdlib_module_names]
        other = [r for r in dropped if r not in std]
        parts = ([f"no longer uses {names(std)}"] if std else []) + (
            [f"adds {names(added_std)}"] if added_std else [])
        if parts:
            emit("PC103", f"`{uname}` changes standard-library modules: {'; '.join(parts)}"
                 + (f"; no longer uses {names(other)}" if other else ""), uu.func.lineno, severity="low")
        else:
            emit("PC103", f"`{uname}` no longer uses {names(other)} (not in the pattern's `requires`)",
                 uu.func.lineno, severity="low")

    # PC101 / PC104: exception handling ------------------------------------
    p_handlers, u_handlers = codeunit.handlers(pu), codeunit.handlers(uu)
    reported: set[str] = set()
    for h, types, _ in p_handlers:
        if codeunit.is_broad(h, types):
            if not any(codeunit.is_broad(uh, ut) for uh, ut, _ in u_handlers):
                emit("PC101", f"`{uname}` no longer has the pattern's catch-all `except`",
                     u_handlers[0][0].lineno if u_handlers else uu.func.lineno)
                attributed_p.add(id(h))
            continue
        for t in types:
            key = name_key(t)
            if key in reported or key in suppressed["catch"]:
                if key in suppressed["catch"]:
                    attributed_p.add(id(h))
                continue
            if not any(codeunit.catches(ut, uh, t) for uh, ut, _ in u_handlers):
                if any(uu.is_unresolved(x) and codeunit.last_segment(x) == codeunit.last_segment(t)
                       for _, ut, _ in u_handlers for x in ut):
                    skipped.append(f"PC101 `{t}`")
                    reported.add(key)
                    attributed_p.add(id(h))
                    continue
                reported.add(key)
                attributed_p.add(id(h))
                line = guards._related_handler_line(u_handlers, t) or uu.func.lineno
                attributed_lines.add(line)
                now = guards._handler_summary(u_handlers)
                pattern_except = in_user_names(h.type, al.global_names)
                emit("PC101", f"`{uname}` no longer catches `{user_spelling(t, uu)}`{now}; the "
                     f"pattern does: `except {pattern_except}`", line)
    p_broad = sum(1 for h, t, _ in p_handlers if codeunit.is_broad(h, t))
    u_broad = [(h, f) for h, t, f in u_handlers if codeunit.is_broad(h, t)]
    for h, f in u_broad[p_broad:]:
        attributed_u.add(id(h))
        attributed_lines.add(h.lineno)
        what = "a bare `except:`" if h.type is None else f"`except {ast.unparse(h.type)}`"
        emit("PC104", f"`{f.name}` adds {what}, which also hides unexpected errors", h.lineno, f.name)

    # PC102: raises and validation branches --------------------------------
    p_raises, u_raises = _raise_records(pu), _raise_records(uu)
    free = list(u_raises)
    leftover = []
    for r in p_raises:
        hit = next((u for u in free if u["kind"] == r["kind"] and u["cond"] == r["cond"]), None)
        if hit is None:
            leftover.append(r)
        else:
            free.remove(hit)
    for r in leftover:
        hit = next((u for u in free if u["kind"] == r["kind"]), None)
        if hit is None:
            hit = next((u for u in free if uu.is_unresolved(u["dotted"]) and codeunit.last_segment(u["dotted"])
                        == codeunit.last_segment(r["dotted"])), None)
            if hit is not None:
                skipped.append(f"PC102 `raise {r['display']}`")
        if hit is not None:
            free.remove(hit)
            continue
        mapping = al.rename_map(r["func"])
        # v5.1: the same check still raises, but a different exception: changed, not removed
        swap = next((u for u in free if u["cond"] == r["cond"] and "<" not in u["kind"] + r["kind"]), None)
        if swap is not None:
            free.remove(swap)
            attributed_p.add(id(r["node"]))
            attributed_lines.add(swap["node"].lineno)
            where = (f" for the check `if {_short(in_user_names(r['if'].test, mapping), 70)}`"
                     if r["if"] is not None else "")
            emit("PC102", f"`{swap['func'].name}` raises `{swap['display']}` instead of the pattern's "
                 f"`{user_spelling(r['dotted'], uu)}`{where}; callers that catch the pattern's exception "
                 f"will not catch it", swap["node"].lineno, swap["func"].name, severity="medium")
            continue
        attributed_p.add(id(r["node"]))
        if r["if"] is not None:
            attributed_p.add(id(r["if"]))
            test = _short(in_user_names(r["if"].test, mapping), 70)
            what = f"the check `if {test}: raise {r['display']}(...)`"
        elif r["kind"] == "<reraise>":
            what = "a re-raise (`raise`) of the caught error"
        else:
            what = f"`raise {r['display']}`"
        emit("PC102", f"`{uname}` dropped {what} from the pattern", uu.func.lineno)

    # PC105 / PC108: calls -------------------------------------------------
    p_calls = codeunit.calls(pu)
    u_calls = codeunit.calls(uu)
    p_keys = {c.key: c for c in reversed(p_calls)}
    u_keys = {c.key: c for c in reversed(u_calls)}
    helper_names = {h.name for h in pu.helpers}
    maybe_added: set[str] = set()
    for key in sorted(set(p_keys) - set(u_keys)):
        if key in suppressed["call"]:
            continue
        maybe = [k for k, c in u_keys.items() if k not in p_keys and uu.is_unresolved(c.dotted)
                 and codeunit.last_segment(c.dotted) == codeunit.last_segment(p_keys[key].dotted)]
        if maybe:
            skipped.append(f"PC105 `{p_keys[key].display}`")
            maybe_added.update(maybe)
            continue
        emit("PC105", f"`{uname}` no longer calls `{user_spelling(p_keys[key].display, uu)}` (the pattern does)",
             uu.func.lineno)
    for key in sorted(set(u_keys) - set(p_keys), key=lambda k: (u_keys[k].line, k)):
        if key in suppressed["nocall"] or key in helper_names or key in maybe_added:
            continue
        c = u_keys[key]
        attributed_lines.add(c.line)
        emit("PC108", f"`{c.func}` adds a call to `{c.display}`", c.line, c.func)

    # PC106: private access ------------------------------------------------
    p_priv = _private_names(pu)
    for shown, (line, fname) in sorted(_private_names(uu).items(), key=lambda x: (x[1][0], x[0])):
        if shown not in p_priv:
            attributed_lines.add(line)
            emit("PC106", f"`{fname}` uses private `{shown.lstrip('.')}`"
                 + (" (an attribute)" if shown.startswith(".") else ""), line, fname)

    # PC107 / PC109: signature ---------------------------------------------
    p_sig, u_sig = _default_key(pu.func, pu), _default_key(uu.func, uu)
    params = al.params
    for pname, (pkind, pshape, pexact) in p_sig.items():
        if pname.startswith("*"):
            continue
        uname_p = params.get(pname)
        if uname_p is None or uname_p not in u_sig:
            emit("PC107", f"`{uname}` dropped parameter `{pname}`", uu.func.lineno)
            continue
        ukind, ushape, uexact = u_sig[uname_p]
        if ukind != pkind:
            emit("PC107", f"parameter `{uname_p}` of `{uname}` is now {ukind} (pattern: {pkind})",
                 uu.func.lineno)
        if pshape != ushape:
            if not pexact:
                what = f"gained a default `{uexact}`"
            elif not uexact:
                what = f"lost its default (pattern: `{pexact}`)"
            else:
                what = f"default changed from `{pexact}` to `{uexact}`"
            emit("PC107", f"parameter `{uname_p}` of `{uname}`: {what}", uu.func.lineno)
        elif pexact != uexact and pname not in suppressed["value"]:
            emit("PC109", f"default of `{uname_p}` changed from `{pexact}` to `{uexact}`", uu.func.lineno)
    mapped_u = set(params.values())
    for upname in u_sig:
        if not upname.startswith("*") and upname not in mapped_u:
            emit("PC107", f"`{uname}` adds parameter `{upname}`", uu.func.lineno)
    for star, label in (("vararg", "*"), ("kwarg", "**")):
        p_star, u_star = getattr(pu.func.args, star), getattr(uu.func.args, star)
        if p_star and not u_star:
            emit("PC107", f"`{uname}` dropped `{label}{p_star.arg}`", uu.func.lineno)
        elif u_star and not p_star:
            emit("PC107", f"`{uname}` adds `{label}{u_star.arg}`", uu.func.lineno)

    # PC109: constants -----------------------------------------------------
    for pname, uname_c in al.constants.items():
        if pname in suppressed["value"]:
            continue
        pv, uv = pu.constants[pname], uu.constants[uname_c]
        if pv != uv:
            label = f"`{uname_c}`" + (f" (pattern: `{pname}`)" if uname_c != pname else "")
            emit("PC109", f"{label} changed from {pv!r} to {uv!r}", uu.constant_nodes[uname_c].lineno)

    # Structure: statements (PC109 literals, PC110) ----------------------------
    shape_match = not al.removed_helpers and not al.added_helpers
    for pf, uf in al.functions:
        pe, ue = entries(pf, pu), entries(uf, uu)
        mapping = al.rename_map(pf)
        matcher = difflib.SequenceMatcher(None, [e.shape for e in pe], [e.shape for e in ue], autojunk=False)
        close = matcher.ratio() >= LITERAL_REPORT_RATIO
        added_total, removed_total, first_line, example = 0, 0, None, None
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                if not close:
                    continue
                for a, b in zip(pe[i1:i2], ue[j1:j2]):
                    if a.exact != b.exact:
                        la, lb = _literals(a.node), _literals(b.node)
                        pair = next(((x, y) for x, y in zip(la, lb) if x != y), None)
                        change = f"{pair[0]!r} -> {pair[1]!r}" if pair else "a literal value"
                        emit("PC109", f"`{uf.name}`: literal changed ({_short(change, 60)}) in "
                             f"`{_short(b.text, 60)}`", getattr(b.node, "lineno", uf.lineno), uf.name)
                continue
            shape_match = False
            removed, added = pe[i1:i2], ue[j1:j2]
            # v4.1: a line that already carries another deviation is never reported again as PC110
            devlines = attributed_lines | {d.line for d in devs}
            added_free = [e for e in added if id(e.node) not in attributed_u
                          and getattr(e.node, "lineno", None) not in devlines]
            if not added_free and (all(id(e.node) in attributed_p for e in removed)
                                   or (added and len(removed) <= len(added))):
                continue
            line = (getattr(added_free[0].node, "lineno", None) if added_free else None) or (
                getattr(ue[j1 - 1].node, "end_lineno", None) if j1 > 0 else None) or uf.lineno
            if not added_free and line in devlines:
                continue
            added_total += len(added_free)
            removed_total += len(removed)
            if first_line is None:
                first_line = line
                if added_free:
                    example = f"e.g. `{_short(added_free[0].text, 60)}`"
                else:
                    text = in_user_names(removed[0].node, mapping).splitlines()[0]
                    example = f"e.g. missing `{_short(text, 60)}`"
        if first_line is not None:
            emit("PC110", f"`{uf.name}` differs from the pattern's structure: {added_total} statement(s) "
                 f"added, {removed_total} pattern statement(s) missing or changed ({example})",
                 first_line, uf.name)
    for h in al.removed_helpers:
        emit("PC110", f"`{uname}` no longer uses the pattern's helper `{h.name}`", uu.func.lineno)
        shape_match = False
    for h in al.added_helpers:
        emit("PC110", f"`{uname}` calls a new helper `{h.name}`", h.lineno, h.name)
    if any(d.code == "PC107" for d in devs):
        shape_match = False

    devs = _dedupe(devs)
    return Analysis(pattern_key, pattern_function, uname, uu.func.lineno, devs,
                    unified_diff(pu, uu, al, pattern_key), shape_match, len(guard_results),
                    uu.resolution, sorted(uu.unknown), assumed, sorted(set(skipped)))


def _dedupe(devs: list[Deviation]) -> list[Deviation]:
    seen = set()
    out = []
    for d in sorted(devs, key=lambda d: (-SEVERITY_RANK[d.severity], d.code, d.line, d.message)):
        key = (d.code, d.message, d.line)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def unified_diff(pu: Unit, uu: Unit, al: Alignment, pattern_key: str) -> str:
    """Pattern unit rendered in the user's names vs the user's unit (comments/docstrings removed)."""
    p_lines: list[str] = []
    for name in pu.constants:
        p_lines.append(in_user_names(pu.constant_nodes[name], al.global_names))
    for pf, _ in al.functions:
        p_lines.extend(in_user_names(pf, al.rename_map(pf)).splitlines())
    for h in al.removed_helpers:
        p_lines.extend(in_user_names(h, al.global_names).splitlines())
    u_lines: list[str] = []
    for name in uu.constants:
        u_lines.append(ast.unparse(uu.constant_nodes[name]))
    for _, uf in al.functions:
        u_lines.extend(ast.unparse(_strip_docstrings(copy.deepcopy(uf))).splitlines())
    for h in al.added_helpers:
        u_lines.extend(ast.unparse(_strip_docstrings(copy.deepcopy(h))).splitlines())
    diff = list(difflib.unified_diff(p_lines, u_lines, f"{pattern_key} (in your names)",
                                     f"your {uu.func.name}", n=1, lineterm=""))
    if len(diff) > MAX_DIFF_LINES:
        diff = diff[:MAX_DIFF_LINES] + [f"... ({len(diff) - MAX_DIFF_LINES} more diff lines)"]
    return "\n".join(diff) + ("\n" if diff else "")


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #


def pattern_unit(pattern, function: str) -> Unit:
    return codeunit.build_unit_from_source(pattern.impl_path.read_text(encoding="utf-8"), function)


def choose_pattern_function(node: ast.FunctionDef, pattern) -> str:
    """The pattern function `node` derives from: same name, else the most similar."""
    meta = pattern.meta
    public = [meta.entry_point, *meta.exports]
    if node.name in public:
        return node.name
    if len(public) == 1:
        return public[0]
    from pcat import provenance

    text = provenance.shape_text(node)
    tree = ast.parse(pattern.impl_path.read_text(encoding="utf-8"))
    best = (-1.0, meta.entry_point)
    for stmt in tree.body:
        if isinstance(stmt, codeunit.FUNC_TYPES) and stmt.name in public and text is not None:
            from pcat import variance

            sim = variance.similarity(text, provenance.shape_text(stmt) or "")
            if sim > best[0] or (sim == best[0] and public.index(stmt.name) < public.index(best[1])):
                best = (sim, stmt.name)
    return best[1]


def analyze_function(tree: ast.Module, node: ast.FunctionDef, pattern,
                     pattern_function: str | None = None, *, module: str | None = None,
                     context: ast.Module | None = None) -> Analysis:
    """Deviations of function `node` (in module `tree`) from catalog `pattern`.
    `module`: the file's dotted module path; `context`: the surrounding file when
    `tree` is a fragment (see `codeunit.build_unit`)."""
    function = pattern_function or choose_pattern_function(node, pattern)
    return analyze(pattern_unit(pattern, function), codeunit.build_unit(tree, node, module, context),
                   pattern_key=pattern.meta.key, pattern_function=function, meta=pattern.meta)
