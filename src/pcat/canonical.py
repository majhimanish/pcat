"""Canonicalization, fingerprinting, name maps and rendering of Python patterns.

The rules in this module define every fingerprint in the catalog. Any change to
the output of `canonicalize` changes fingerprints and requires a deliberate
migration of every pattern (see CLAUDE.md, "Invariants").

Input is a module that contains only imports and top-level function
definitions (plus an optional module docstring). The pipeline is:

1. parse with `ast.parse`
2. remove docstrings (leading string-constant statements of modules/functions)
3. optionally strip type annotations (`keep_annotations=False`)
4. split, sort and deduplicate top-level imports
5. order functions: entry point first, then helpers in source order
6. rename top-level functions to f0, f1, ... and each function's parameters and
   local variables to v0, v1, ... (numbering restarts in every function)
7. `ast.unparse`, then exactly one trailing newline

Name-map keys: "fN" for function names, "vM" for locals of the entry point
(f0), and "fN.vM" for locals of helper fN (N >= 1). "f0.vM" is accepted as an
alias of "vM" when rendering.
"""

from __future__ import annotations

import ast
import hashlib
import keyword
import re
from collections.abc import Iterator
from dataclasses import dataclass

from pcat.errors import CanonicalizationError, RenderError

PLACEHOLDER_RE = re.compile(r"^[fv]\d+$")
_FUNC_RE = re.compile(r"^f\d+$")
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
    imports, funcs = _split_module(tree)
    imports = _normalize_imports(imports)
    funcs = _order_functions(funcs, entry_point)

    fmap = {func.name: f"f{i}" for i, func in enumerate(funcs)}
    module_bound = {_alias_bound_name(a) for imp in imports for a in imp.names}
    module_bound.discard("*")
    for name in sorted(module_bound):
        if PLACEHOLDER_RE.match(name):
            raise CanonicalizationError(
                f"imported name {name!r} collides with the placeholder namespace (f0, v0, ...)"
            )

    name_map: dict[str, str] = {}
    for func in funcs:
        placeholder = fmap[func.name]
        locals_, excluded = _scope_names(func)
        local_map = _number_locals(func, locals_)
        _check_collisions(func, local_map, fmap, excluded)

        name_map[placeholder] = func.name
        prefix = "" if placeholder == "f0" else f"{placeholder}."
        for real, ph in local_map.items():
            name_map[f"{prefix}{ph}"] = real

        _apply_renames(func, placeholder, fmap, local_map, excluded)

    text = _unparse(imports, funcs)
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
    """Return {"f0": "binary_search", "v0": "items", "f1.v0": ...} for `source`."""
    return analyze(source, entry_point, keep_annotations).name_map


def list_functions(source: str) -> list[str]:
    """Names of the top-level functions in `source`, in source order.

    Raises CanonicalizationError if the module contains anything other than
    imports, functions and a module docstring at top level.
    """
    tree = _parse(source)
    _strip_docstrings(tree)
    _, funcs = _split_module(tree)
    return [f.name for f in funcs]


def render(canonical_text: str, name_map: dict[str, str]) -> str:
    """Replace placeholders in `canonical_text` with names from `name_map`.

    Works on the AST (never on raw text). Placeholders missing from the map are
    left as they are. Unknown keys and invalid identifiers raise RenderError.
    """
    for key, value in name_map.items():
        if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value):
            raise RenderError(f"name for {key!r} is not a valid Python identifier: {value!r}")

    try:
        tree = _parse(canonical_text)
    except CanonicalizationError as exc:
        raise RenderError(f"canonical text does not parse: {exc}") from None
    imports, funcs = _split_module(tree)
    func_names = [f.name for f in funcs]
    bad = [n for n in func_names if not _FUNC_RE.match(n)]
    if bad:
        raise RenderError(f"not a canonical form: function {bad[0]!r} is not a placeholder")

    scopes: dict[str, set[str]] = {}
    for func in funcs:
        locals_, _ = _scope_names(func)
        scopes[func.name] = locals_

    fmap: dict[str, str] = {}
    local_maps: dict[str, dict[str, str]] = {name: {} for name in func_names}
    for key, value in name_map.items():
        if _FUNC_RE.match(key):
            if key not in scopes:
                raise RenderError(f"unknown placeholder {key!r}: no such function")
            fmap[key] = value
            continue
        m = _KEY_RE.match(key)
        if not m:
            raise RenderError(f"invalid name-map key {key!r}; expected fN, vM or fN.vM")
        owner = m.group(1) or "f0"
        var = m.group(2)
        if owner not in scopes or var not in scopes[owner]:
            raise RenderError(f"unknown placeholder {key!r}")
        local_maps[owner][var] = value

    for func in funcs:
        _apply_renames(func, fmap.get(func.name, func.name), fmap, local_maps[func.name], set())
    return _unparse(imports, funcs)


def extract_function(source: str, name: str) -> str:
    """Return source for top-level function `name`, the helpers it uses and its imports.

    Helpers are other top-level functions referenced (transitively) by name.
    Only imports whose bound names are referenced are kept; star imports are
    always kept. Function bodies are copied verbatim, so comments survive.
    Other top-level statements of the file are ignored.
    """
    tree = _parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, _FUNC_TYPES)}
    if name not in funcs:
        raise CanonicalizationError(f"no top-level function named {name!r}")

    selected: set[str] = set()
    todo = [name]
    while todo:
        current = todo.pop()
        if current in selected:
            continue
        selected.add(current)
        for ref in _referenced_names(funcs[current]):
            if ref in funcs and ref not in selected:
                todo.append(ref)

    ordered = [n for n in tree.body if isinstance(n, _FUNC_TYPES) and n.name in selected]
    used: set[str] = set()
    for func in ordered:
        used |= _referenced_names(func)

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
    for func in ordered:
        start = min([func.lineno] + [d.lineno for d in func.decorator_list])
        chunks.append("".join(lines[start - 1 : func.end_lineno]).rstrip() + "\n")

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


def _split_module(tree: ast.Module) -> tuple[list[ast.stmt], list[ast.FunctionDef]]:
    imports: list[ast.stmt] = []
    funcs: list[ast.FunctionDef] = []
    seen: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, _IMPORT_TYPES):
            imports.append(stmt)
        elif isinstance(stmt, _FUNC_TYPES):
            if stmt.name in seen:
                raise CanonicalizationError(
                    f"line {stmt.lineno}: function {stmt.name!r} is defined twice"
                )
            seen.add(stmt.name)
            funcs.append(stmt)
        else:
            raise CanonicalizationError(
                f"line {stmt.lineno}: only imports and function definitions are allowed "
                f"at top level, found {type(stmt).__name__}"
            )
    if not funcs:
        raise CanonicalizationError("no top-level function found")
    return imports, funcs


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


def _body_nodes(func: ast.FunctionDef) -> Iterator[ast.AST]:
    for stmt in func.body:
        yield from ast.walk(stmt)


def _scope_names(func: ast.FunctionDef) -> tuple[set[str], set[str]]:
    """Return (renameable local names, names that must never be renamed).

    All bindings anywhere inside the function (including nested functions,
    lambdas and comprehensions) form one flat scope. This is a consistent
    bijective rename, so it preserves behaviour.
    """
    bound = {a.arg for a in _arg_nodes(func.args)}
    excluded: set[str] = set()
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
            excluded.update(_alias_bound_name(a) for a in node.names)
        elif isinstance(node, ast.Global):
            excluded.update(node.names)
    locals_ = {
        n for n in bound - excluded if n not in _NEVER_RENAME and not _is_dunder(n)
    }
    return locals_, excluded


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


def _check_collisions(func, local_map, fmap, excluded) -> None:
    """Reject names that would be confused with placeholders after renaming."""
    everything = list(_identifiers(func))
    for ident in everything:
        if ident in local_map and ident not in excluded:
            continue
        if ident in fmap:
            continue
        if PLACEHOLDER_RE.match(ident):
            raise CanonicalizationError(
                f"function {func.name!r}: name {ident!r} is not renamed and collides with "
                "the placeholder namespace (f0, v0, ...)"
            )


class _Renamer(ast.NodeTransformer):
    """Rename functions (fmap) and one function's locals (local_map)."""

    def __init__(self, fmap: dict[str, str], local_map: dict[str, str], excluded: set[str]):
        self.fmap = fmap
        self.local_map = local_map
        self.excluded = excluded

    def _map(self, name: str) -> str:
        if name in self.local_map:
            return self.local_map[name]
        if name in self.excluded:
            return name
        return self.fmap.get(name, name)

    def visit_Name(self, node: ast.Name) -> ast.Name:  # noqa: N802
        node.id = self._map(node.id)
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


def _apply_renames(func, new_name, fmap, local_map, excluded) -> None:
    """Rename a top-level function in place.

    Decorators, defaults and signature annotations are evaluated in module
    scope, so they only see function renames. Parameters and the body see the
    function's local renames too.
    """
    module_scope = _Renamer(fmap, {}, set())
    func_scope = _Renamer(fmap, local_map, excluded)

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


def _unparse(imports: list[ast.stmt], funcs: list[ast.FunctionDef]) -> str:
    module = ast.Module(body=[*imports, *funcs], type_ignores=[])
    ast.fix_missing_locations(module)
    return ast.unparse(module).strip("\n") + "\n"


def _referenced_names(func: ast.FunctionDef) -> set[str]:
    return {n.id for n in ast.walk(func) if isinstance(n, ast.Name)}
