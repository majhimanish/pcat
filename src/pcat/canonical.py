"""Canonicalization, fingerprinting, name maps and rendering of Python patterns.

The rules in this module define every fingerprint in the catalog. Any change
that can alter the output of `canonicalize` must bump `CANONICAL_VERSION` and
be followed by `pcat migrate-fingerprints` (see CLAUDE.md, "Invariants").

Input is a module that contains only imports, top-level function definitions
and literal constants (`NAME = <literal>` or `NAME: T = <literal>`, where the
value is accepted by `ast.literal_eval`), plus an optional module docstring.
The pipeline is:

1. parse with `ast.parse`
2. remove docstrings (leading string-constant statements of modules/functions)
3. optionally strip type annotations (`keep_annotations=False`)
4. split, sort and deduplicate top-level imports; they always come first
5. then constants in source order, then functions: entry point first, helpers
   in source order (constants are literals, so placing them before every
   function keeps defaults/decorators that use them runnable)
6. rename top-level functions to f0, f1, ..., constants to c0, c1, ... (source
   order), and each function's parameters and locals to v0, v1, ... (numbering
   restarts in every function). Keyword arguments in calls to functions defined
   in the snippet are renamed with the callee's placeholders.
7. `ast.unparse`, then exactly one trailing newline

Name-map keys: "fN" for function names, "cN" for constants, "vM" for locals of
the entry point (f0), and "fN.vM" for locals of helper fN (N >= 1). "f0.vM" is
accepted as an alias of "vM" when rendering.
"""

from __future__ import annotations

import ast
import hashlib
import keyword
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from pcat.errors import CanonicalizationError, RenderError

# Version of the rules in this module. v1 = the original rules (spec v1);
# v2 = keyword arguments at calls to snippet functions renamed, literal
# constants allowed and renamed to cN. Bump on any change that can alter any
# fingerprint, then run `pcat migrate-fingerprints`.
CANONICAL_VERSION = 2

PLACEHOLDER_RE = re.compile(r"^[fvc]\d+$")
_FUNC_RE = re.compile(r"^f\d+$")
_CONST_RE = re.compile(r"^c\d+$")
_KEY_RE = re.compile(r"^(?:(f\d+)\.)?(v\d+)$")

_FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
_IMPORT_TYPES = (ast.Import, ast.ImportFrom)
_NEVER_RENAME = frozenset({"self", "cls"})


@dataclass(frozen=True)
class CanonicalResult:
    """Canonical text, its fingerprint and the placeholder -> real name map."""

    text: str
    fingerprint: str
    name_map: dict[str, str]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def analyze(
    source: str, entry_point: str | None = None, keep_annotations: bool = True
) -> CanonicalResult:
    """Canonicalize `source` and return text, fingerprint and name map.

    `entry_point` is the real name of the function that becomes f0. When it is
    None, the first top-level function in source order is the entry point.
    """
    tree = _parse(source)
    _strip_docstrings(tree)
    if not keep_annotations:
        tree = _AnnotationStripper().visit(tree)
        _fix_empty_bodies(tree)
    mod = _split_module(tree)
    imports = _normalize_imports(mod.imports)
    funcs = _order_functions(mod.funcs, entry_point)
    body = [*mod.consts, *funcs]

    fmap = {func.name: f"f{i}" for i, func in enumerate(funcs)}
    cmap = {_const_name(c): f"c{i}" for i, c in enumerate(mod.consts)}
    module_map = {**fmap, **cmap}
    module_bound = {_alias_bound_name(a) for imp in imports for a in imp.names}
    module_bound.discard("*")
    for name in sorted(module_bound):
        if PLACEHOLDER_RE.match(name):
            raise CanonicalizationError(
                f"imported name {name!r} collides with the placeholder namespace "
                "(f0, c0, v0, ...)"
            )

    # Scope analysis of every function first, so that calls can be resolved
    # regardless of definition order.
    scopes: dict[str, _Scope] = {}
    for func in funcs:
        scope = _scope_names(func)
        scope.local_map = _number_locals(func, scope.locals)
        scopes[func.name] = scope
    kw_maps = {
        func.name: _keyword_map(func, scopes[func.name].local_map) for func in funcs
    }

    for const in mod.consts:
        _check_collisions(const, set(module_map), f"constant {_const_name(const)!r}")

    name_map: dict[str, str] = {}
    for func in funcs:
        placeholder = fmap[func.name]
        scope = scopes[func.name]
        _check_collisions(
            func, set(scope.local_map) | set(module_map), f"function {func.name!r}"
        )
        name_map[placeholder] = func.name
        prefix = "" if placeholder == "f0" else f"{placeholder}."
        for real, ph in scope.local_map.items():
            name_map[f"{prefix}{ph}"] = real
    for real, ph in cmap.items():
        name_map[ph] = real

    for func in funcs:
        scope = scopes[func.name]
        _apply_renames(func, fmap[func.name], module_map, scope.local_map, scope.imported, kw_maps)
    for const in mod.consts:
        _rename_constant(const, cmap[_const_name(const)], module_map, kw_maps)

    text = _unparse(imports, body)
    return CanonicalResult(text=text, fingerprint=fingerprint(text), name_map=name_map)


def canonicalize(
    source: str, entry_point: str | None = None, keep_annotations: bool = True
) -> str:
    """Return the canonical form of `source` (see module docstring)."""
    return analyze(source, entry_point, keep_annotations).text


def fingerprint(canonical_text: str) -> str:
    """SHA-256 hex digest of canonical text encoded as UTF-8."""
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def extract_name_map(
    source: str, entry_point: str | None = None, keep_annotations: bool = True
) -> dict[str, str]:
    """Return {"f0": "binary_search", "v0": "items", "f1.v0": ..., "c0": ...}."""
    return analyze(source, entry_point, keep_annotations).name_map


def list_functions(source: str) -> list[str]:
    """Names of the top-level functions in `source`, in source order.

    Raises CanonicalizationError if the module contains anything other than
    imports, functions, literal constants and a module docstring at top level.
    """
    tree = _parse(source)
    _strip_docstrings(tree)
    return [f.name for f in _split_module(tree).funcs]


def render(canonical_text: str, name_map: dict[str, str]) -> str:
    """Replace placeholders in `canonical_text` with names from `name_map`.

    Works on the AST (never on raw text). Placeholders missing from the map are
    left as they are. Keyword arguments at calls to snippet functions follow the
    callee's names. Unknown keys and invalid identifiers raise RenderError.
    """
    for key, value in name_map.items():
        if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value):
            raise RenderError(f"name for {key!r} is not a valid Python identifier: {value!r}")

    try:
        tree = _parse(canonical_text)
        mod = _split_module(tree)
    except CanonicalizationError as exc:
        raise RenderError(f"not a canonical form: {exc}") from None
    func_names = [f.name for f in mod.funcs]
    bad = [n for n in func_names if not _FUNC_RE.match(n)]
    bad += [_const_name(c) for c in mod.consts if not _CONST_RE.match(_const_name(c))]
    if bad:
        raise RenderError(f"not a canonical form: {bad[0]!r} is not a placeholder")
    const_names = {_const_name(c) for c in mod.consts}

    scopes = {func.name: _scope_names(func) for func in mod.funcs}
    module_map: dict[str, str] = {}
    local_maps: dict[str, dict[str, str]] = {name: {} for name in func_names}
    for key, value in name_map.items():
        if _FUNC_RE.match(key):
            if key not in scopes:
                raise RenderError(f"unknown placeholder {key!r}: no such function")
            module_map[key] = value
            continue
        if _CONST_RE.match(key):
            if key not in const_names:
                raise RenderError(f"unknown placeholder {key!r}: no such constant")
            module_map[key] = value
            continue
        m = _KEY_RE.match(key)
        if not m:
            raise RenderError(f"invalid name-map key {key!r}; expected fN, cN, vM or fN.vM")
        owner = m.group(1) or "f0"
        var = m.group(2)
        if owner not in scopes or var not in scopes[owner].locals:
            raise RenderError(f"unknown placeholder {key!r}")
        local_maps[owner][var] = value

    kw_maps = {func.name: _keyword_map(func, local_maps[func.name]) for func in mod.funcs}
    for func in mod.funcs:
        _apply_renames(
            func,
            module_map.get(func.name, func.name),
            module_map,
            local_maps[func.name],
            scopes[func.name].imported,
            kw_maps,
        )
    for const in mod.consts:
        name = _const_name(const)
        _rename_constant(const, module_map.get(name, name), module_map, kw_maps)
    return _unparse(mod.imports, mod.body)


def extract_function(source: str, name: str | Sequence[str]) -> str:
    """Return source for top-level function `name` (or several) and everything it needs.

    `name` may be a list of function names; each is extracted as if on its own
    and the results are merged (a pattern can export e.g. hash and verify). For
    a single name the output is unchanged.

    That is: other top-level functions it references (transitively), the
    literal constants those functions use, and the imports whose bound names
    they use (star imports are always kept). Functions and constants are copied
    verbatim in source order, so comments inside functions survive. Raises
    CanonicalizationError if a function uses a module-level name that is bound
    by anything other than a literal constant, a function or an import.
    """
    tree = _parse(source)
    funcs: dict[str, ast.stmt] = {}
    consts: dict[str, ast.stmt] = {}
    binding_count: dict[str, int] = {}
    for stmt in tree.body:
        if isinstance(stmt, _IMPORT_TYPES):
            continue
        names = _top_level_bindings(stmt)
        for bound in names:
            binding_count[bound] = binding_count.get(bound, 0) + 1
        if isinstance(stmt, _FUNC_TYPES):
            funcs[stmt.name] = stmt
        elif _is_literal_constant(stmt):
            consts[_const_name(stmt)] = stmt
    names = [name] if isinstance(name, str) else list(dict.fromkeys(name))
    if not names:
        raise CanonicalizationError("no function names given")
    for wanted in names:
        if wanted not in funcs:
            raise CanonicalizationError(f"no top-level function named {wanted!r}")

    selected: set[str] = set()
    used: set[str] = set()
    todo = list(reversed(names))
    while todo:
        current = todo.pop()
        if current in selected:
            continue
        selected.add(current)
        for ref in sorted(_free_names(funcs[current])):
            used.add(ref)
            if binding_count.get(ref, 0) > 1:
                raise CanonicalizationError(
                    f"function {current!r} uses module-level name {ref!r}, which is bound "
                    "more than once at top level; only a single NAME = <literal> "
                    "constant can be copied into a pattern"
                )
            if ref in funcs:
                todo.append(ref)
            elif ref in consts:
                selected.add(ref)
            elif ref in binding_count:
                raise CanonicalizationError(
                    f"function {current!r} uses module-level name {ref!r}, which is not "
                    "a literal constant; only NAME = <literal> constants (see "
                    "ast.literal_eval) can be copied into a pattern"
                )

    import_lines: list[str] = []
    for stmt in tree.body:
        if not isinstance(stmt, _IMPORT_TYPES):
            continue
        kept = [a for a in stmt.names if a.name == "*" or _alias_bound_name(a) in used]
        if kept:
            clone = (
                ast.Import(names=kept)
                if isinstance(stmt, ast.Import)
                else ast.ImportFrom(module=stmt.module, names=kept, level=stmt.level)
            )
            line = ast.unparse(clone)
            if line not in import_lines:
                import_lines.append(line)

    lines = source.splitlines(keepends=True)
    chunks = []
    for stmt in tree.body:
        if isinstance(stmt, _FUNC_TYPES) and stmt.name in selected:
            start = min([stmt.lineno] + [d.lineno for d in stmt.decorator_list])
            chunks.append("".join(lines[start - 1 : stmt.end_lineno]).rstrip() + "\n")
        elif stmt in consts.values() and _const_name(stmt) in selected:
            chunks.append(ast.get_source_segment(source, stmt) + "\n")

    parts = []
    if import_lines:
        parts.append("\n".join(import_lines) + "\n")
    parts.extend(chunks)
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Pipeline steps
# --------------------------------------------------------------------------- #


def _parse(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise CanonicalizationError(f"syntax error at line {exc.lineno}: {exc.msg}") from None
    except ValueError as exc:  # e.g. null bytes
        raise CanonicalizationError(f"cannot parse source: {exc}") from None


def _is_string_expr(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _strip_docstrings(tree: ast.Module) -> None:
    """Remove all leading string statements of the module and every function."""
    for node in list(ast.walk(tree)):
        if isinstance(node, (ast.Module, *_FUNC_TYPES)):
            while node.body and _is_string_expr(node.body[0]):
                node.body.pop(0)
            if not node.body and not isinstance(node, ast.Module):
                node.body.append(ast.Pass())


class _AnnotationStripper(ast.NodeTransformer):
    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.annotation = None
        return node

    def visit_FunctionDef(self, node):  # noqa: N802 - ast visitor naming
        node.returns = None
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_AnnAssign(self, node: ast.AnnAssign):  # noqa: N802
        if node.value is None:
            return None
        value = self.visit(node.value)
        return ast.copy_location(ast.Assign(targets=[node.target], value=value), node)


def _fix_empty_bodies(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and not body and not isinstance(node, ast.Module):
            body.append(ast.Pass())


def _is_literal_value(node: ast.expr | None) -> bool:
    if node is None:
        return False
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


def _assigned_name(stmt: ast.stmt) -> str | None:
    """NAME for `NAME = value` / `NAME: T = value`, else None."""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        target = stmt.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        return stmt.target.id if isinstance(stmt.target, ast.Name) else None
    return None


def _is_literal_constant(stmt: ast.stmt) -> bool:
    return _assigned_name(stmt) is not None and _is_literal_value(stmt.value)


def _const_name(stmt: ast.stmt) -> str:
    name = _assigned_name(stmt)
    assert name is not None
    return name


def _top_level_bindings(stmt: ast.stmt) -> set[str]:
    """Names a non-import top-level statement binds in the module namespace."""
    if isinstance(stmt, (*_FUNC_TYPES, ast.ClassDef)):
        return {stmt.name}
    names: set[str] = set()
    todo: list[ast.AST] = [stmt]
    while todo:
        node = todo.pop()
        if isinstance(node, (*_FUNC_TYPES, ast.ClassDef)):
            names.add(node.name)  # e.g. a def inside a top-level `if`
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, _IMPORT_TYPES):
            names.update(_alias_bound_name(a) for a in node.names if a.name != "*")
        todo.extend(ast.iter_child_nodes(node))
    return names


@dataclass
class _ModuleParts:
    imports: list[ast.stmt] = field(default_factory=list)
    funcs: list[ast.FunctionDef] = field(default_factory=list)
    consts: list[ast.stmt] = field(default_factory=list)
    body: list[ast.stmt] = field(default_factory=list)  # funcs + consts, source order


def _split_module(tree: ast.Module) -> _ModuleParts:
    parts = _ModuleParts()
    seen: set[str] = set()

    def claim(name: str, stmt: ast.stmt, what: str) -> None:
        if name in seen:
            raise CanonicalizationError(f"line {stmt.lineno}: {what} {name!r} is defined twice")
        seen.add(name)

    for stmt in tree.body:
        if isinstance(stmt, _IMPORT_TYPES):
            parts.imports.append(stmt)
        elif isinstance(stmt, _FUNC_TYPES):
            claim(stmt.name, stmt, "function")
            parts.funcs.append(stmt)
            parts.body.append(stmt)
        elif _assigned_name(stmt) is not None:
            name = _assigned_name(stmt)
            if not _is_literal_value(stmt.value):
                raise CanonicalizationError(
                    f"line {stmt.lineno}: top-level assignment to {name!r} is not a literal "
                    "constant; only NAME = <literal> is allowed (numbers, strings, bytes, "
                    "booleans, None, and tuples/lists/dicts/sets of those)"
                )
            claim(name, stmt, "name")
            parts.consts.append(stmt)
            parts.body.append(stmt)
        else:
            raise CanonicalizationError(
                f"line {stmt.lineno}: only imports, function definitions and literal "
                f"constants are allowed at top level, found {type(stmt).__name__}"
            )
    if not parts.funcs:
        raise CanonicalizationError("no top-level function found")
    return parts


def _normalize_imports(imports: list[ast.stmt]) -> list[ast.stmt]:
    """One alias per statement, deduplicated, sorted (__future__ first)."""
    by_text: dict[str, ast.stmt] = {}
    for stmt in imports:
        for alias in stmt.names:
            if isinstance(stmt, ast.Import):
                single: ast.stmt = ast.Import(names=[alias])
            else:
                single = ast.ImportFrom(module=stmt.module, names=[alias], level=stmt.level)
            by_text.setdefault(ast.unparse(single), single)

    def key(text: str) -> tuple[int, str]:
        return (0 if text.startswith("from __future__ ") else 1, text)

    return [by_text[t] for t in sorted(by_text, key=key)]


def _order_functions(funcs: list[ast.FunctionDef], entry_point: str | None):
    if entry_point is None:
        return list(funcs)
    entry = [f for f in funcs if f.name == entry_point]
    if not entry:
        raise CanonicalizationError(f"entry point {entry_point!r} is not a top-level function")
    return entry + [f for f in funcs if f.name != entry_point]


def _alias_bound_name(alias: ast.alias) -> str:
    return alias.asname or alias.name.split(".")[0]


def _arg_nodes(args: ast.arguments) -> list[ast.arg]:
    nodes = [*args.posonlyargs, *args.args]
    if args.vararg:
        nodes.append(args.vararg)
    nodes.extend(args.kwonlyargs)
    if args.kwarg:
        nodes.append(args.kwarg)
    return nodes


def _keyword_map(func: ast.FunctionDef, local_map: dict[str, str]) -> dict[str, str]:
    """Parameter renames that apply to keyword arguments in calls to `func`.

    Only parameters that can be passed by keyword (regular and keyword-only).
    Positional-only parameters never bind a keyword: with `**kwargs` such a
    keyword lands in kwargs under its literal name, so it must stay unchanged.
    """
    names = [a.arg for a in (*func.args.args, *func.args.kwonlyargs)]
    return {n: local_map[n] for n in names if n in local_map}


def _body_nodes(func: ast.FunctionDef) -> Iterator[ast.AST]:
    for stmt in func.body:
        yield from ast.walk(stmt)


@dataclass
class _Scope:
    locals: set[str]  # renameable local names
    imported: set[str]  # bound by imports inside the function: never renamed
    local_map: dict[str, str] = field(default_factory=dict)


def _scope_names(func: ast.FunctionDef) -> _Scope:
    """Local names of a top-level function.

    All bindings anywhere inside the function (including nested functions,
    lambdas and comprehensions) form one flat scope. This is a consistent
    bijective rename, so it preserves behaviour. Names declared `global` are not
    locals: they resolve to module names (functions, constants) or stay as-is.
    """
    bound = {a.arg for a in _arg_nodes(func.args)}
    imported: set[str] = set()
    globals_: set[str] = set()
    for node in _body_nodes(func):
        if isinstance(node, ast.ClassDef):
            raise CanonicalizationError(
                f"line {node.lineno}: class definitions inside functions are not supported"
            )
        if isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, _FUNC_TYPES):
            bound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
        elif isinstance(node, _IMPORT_TYPES):
            imported.update(_alias_bound_name(a) for a in node.names)
        elif isinstance(node, ast.Global):
            globals_.update(node.names)
    locals_ = {
        n
        for n in bound - imported - globals_
        if n not in _NEVER_RENAME and not _is_dunder(n)
    }
    return _Scope(locals=locals_, imported=imported)


def _free_names(func: ast.FunctionDef) -> set[str]:
    """Names a top-level function reads from the module namespace."""
    scope = _scope_names(func)
    referenced = {n.id for n in ast.walk(func) if isinstance(n, ast.Name)}
    return referenced - scope.locals - scope.imported - _NEVER_RENAME


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def _identifiers(node: ast.AST) -> Iterator[str]:
    """Identifiers bound or referenced at `node`, in deterministic pre-order."""
    if isinstance(node, ast.arg):
        yield node.arg
    elif isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, _FUNC_TYPES):
        yield node.name
    elif isinstance(node, ast.ExceptHandler) and node.name:
        yield node.name
    elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
        yield node.name
    elif isinstance(node, (ast.Nonlocal, ast.Global)):
        yield from node.names
    elif isinstance(node, ast.alias):
        yield _alias_bound_name(node)
    for child in ast.iter_child_nodes(node):
        yield from _identifiers(child)
    if isinstance(node, ast.MatchMapping) and node.rest:
        yield node.rest  # `**rest` comes after the keys' captures, as it reads


def _function_identifiers(func: ast.FunctionDef) -> Iterator[str]:
    """Parameters in signature order, then the body depth-first."""
    for arg in _arg_nodes(func.args):
        yield arg.arg
    for stmt in func.body:
        yield from _identifiers(stmt)


def _number_locals(func: ast.FunctionDef, locals_: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for ident in _function_identifiers(func):
        if ident in locals_ and ident not in mapping:
            mapping[ident] = f"v{len(mapping)}"
    return mapping


def _check_collisions(node: ast.AST, renamed: set[str], where: str) -> None:
    """Reject names that would be confused with placeholders after renaming."""
    for ident in _identifiers(node):
        if ident not in renamed and PLACEHOLDER_RE.match(ident):
            raise CanonicalizationError(
                f"{where}: name {ident!r} is not renamed and collides with the "
                "placeholder namespace (f0, c0, v0, ...)"
            )


class _Renamer(ast.NodeTransformer):
    """Rename module names (functions, constants) and one function's locals.

    `kw_maps` maps a snippet function's (pre-rename) name to the renames of its
    keyword-passable parameters; keyword arguments of calls to it follow them.
    """

    def __init__(
        self,
        module_map: dict[str, str],
        local_map: dict[str, str],
        imported: set[str],
        kw_maps: dict[str, dict[str, str]],
    ):
        self.module_map = module_map
        self.local_map = local_map
        self.imported = imported
        self.kw_maps = kw_maps

    def _map(self, name: str) -> str:
        if name in self.local_map:
            return self.local_map[name]
        if name in self.imported:
            return name
        return self.module_map.get(name, name)

    def visit_Name(self, node: ast.Name) -> ast.Name:  # noqa: N802
        node.id = self._map(node.id)
        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:  # noqa: N802
        callee = None
        func = node.func
        if (
            isinstance(func, ast.Name)
            and func.id not in self.local_map
            and func.id not in self.imported
        ):
            callee = self.kw_maps.get(func.id)
        self.generic_visit(node)
        if callee:
            for kw in node.keywords:
                if kw.arg is not None and kw.arg in callee:
                    kw.arg = callee[kw.arg]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self.local_map.get(node.arg, node.arg)
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):  # noqa: N802 - nested functions only
        node.name = self.local_map.get(node.name, node.name)
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler):  # noqa: N802
        if node.name:
            node.name = self.local_map.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_MatchAs(self, node):  # noqa: N802
        if node.name:
            node.name = self.local_map.get(node.name, node.name)
        self.generic_visit(node)
        return node

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):  # noqa: N802
        if node.rest:
            node.rest = self.local_map.get(node.rest, node.rest)
        self.generic_visit(node)
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.Nonlocal:  # noqa: N802
        node.names = [self.local_map.get(n, n) for n in node.names]
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:  # noqa: N802
        node.names = [self.module_map.get(n, n) for n in node.names]
        return node


def _apply_renames(func, new_name, module_map, local_map, imported, kw_maps) -> None:
    """Rename a top-level function in place.

    Decorators, defaults and signature annotations are evaluated in module
    scope, so they only see module renames. Parameters and the body see the
    function's local renames too.
    """
    module_scope = _Renamer(module_map, {}, set(), kw_maps)
    func_scope = _Renamer(module_map, local_map, imported, kw_maps)

    func.name = new_name
    func.decorator_list = [module_scope.visit(d) for d in func.decorator_list]
    args = func.args
    args.defaults = [module_scope.visit(d) for d in args.defaults]
    args.kw_defaults = [module_scope.visit(d) if d is not None else None for d in args.kw_defaults]
    for arg in _arg_nodes(args):
        if arg.annotation is not None:
            arg.annotation = module_scope.visit(arg.annotation)
        arg.arg = local_map.get(arg.arg, arg.arg)
    if func.returns is not None:
        func.returns = module_scope.visit(func.returns)
    func.body = [func_scope.visit(stmt) for stmt in func.body]


def _rename_constant(stmt: ast.stmt, new_name: str, module_map, kw_maps) -> None:
    target = stmt.targets[0] if isinstance(stmt, ast.Assign) else stmt.target
    target.id = new_name
    if isinstance(stmt, ast.AnnAssign):
        stmt.annotation = _Renamer(module_map, {}, set(), kw_maps).visit(stmt.annotation)


def _unparse(imports: list[ast.stmt], body: list[ast.stmt]) -> str:
    module = ast.Module(body=[*imports, *body], type_ignores=[])
    ast.fix_missing_locations(module)
    return ast.unparse(module).strip("\n") + "\n"
