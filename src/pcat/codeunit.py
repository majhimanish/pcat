"""Code units for guards and deviation analysis (v4). Standard library only.

A *unit* is one function as it sits in its file, plus what it needs from the
same file: top-level functions it calls (transitively), the literal constants
it reads and the import bindings it uses. Unlike `canonical.extract_function`,
building a unit never fails on what else the file contains (classes, scripts,
`if __name__ == "__main__":` blocks); those parts are just not in the unit.

Names are resolved so that comparisons never depend on what the user called
things: locals are anonymous, import-bound names become their dotted origin
(`from hmac import compare_digest` -> `hmac.compare_digest`), and method calls
on values become `.name`.
"""

from __future__ import annotations

import ast
import builtins
import copy
from dataclasses import dataclass, field

from pcat import canonical

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})


@dataclass
class Unit:
    func: ast.FunctionDef
    helpers: list[ast.FunctionDef]  # same-file top-level functions it calls, source order
    constants: dict[str, object]  # literal constants the unit reads: name -> value (source order)
    constant_nodes: dict[str, ast.stmt]
    file_constants: dict[str, object]  # every top-level literal constant of the file
    imports: dict[str, str]  # bound name -> dotted origin (module level + inside the unit)
    undefined_calls: set[str] = field(default_factory=set)  # free names called, defined nowhere
    file_names: set[str] = field(default_factory=set)  # every name bound at the file's top level
    _locals: dict[int, set[str]] = field(default_factory=dict, repr=False)

    @property
    def functions(self) -> list[ast.FunctionDef]:
        return [self.func, *self.helpers]

    @property
    def helper_names(self) -> set[str]:
        return {h.name for h in self.helpers}

    def locals_of(self, func: ast.FunctionDef) -> set[str]:
        key = id(func)
        if key not in self._locals:
            self._locals[key] = local_names(func)
        return self._locals[key]

    def owner(self, node: ast.AST) -> ast.FunctionDef:
        for func in self.functions:
            for inner in ast.walk(func):
                if inner is node:
                    return func
        return self.func

    # ------------------------------------------------------------------ #
    # Name resolution
    # ------------------------------------------------------------------ #

    def resolve(self, expr: ast.expr, func: ast.FunctionDef) -> str | None:
        """Dotted name of `expr` for comparison, or None when it is not a plain name.

        Locals -> None; unit helpers -> "fn:<name>"; constants -> "const:<name>";
        import-bound names -> their origin; other free names stay as they are;
        attribute chains on anything else -> ".attr".
        """
        if isinstance(expr, ast.Name):
            name = expr.id
            if name in self.locals_of(func):
                return None
            if name in self.helper_names or name == self.func.name:
                return f"fn:{name}"
            if name in self.constant_nodes:
                return f"const:{name}"
            return self.imports.get(name, name)
        if isinstance(expr, ast.Attribute):
            base = self.resolve(expr.value, func) if isinstance(expr.value, (ast.Name, ast.Attribute)) else None
            if base is None or base.startswith((".", "fn:", "const:")):
                return f".{expr.attr}"
            return f"{base}.{expr.attr}"
        return None


def name_key(dotted: str) -> str:
    """Comparison key: `requests.exceptions.Timeout` and `requests.Timeout` are equal."""
    if dotted.startswith(".") or "." not in dotted:
        return dotted
    parts = dotted.split(".")
    return f"{parts[0]}.{parts[-1]}"


def import_bindings(nodes: list[ast.stmt]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    out[alias.asname] = alias.name
                else:
                    root = alias.name.split(".")[0]
                    out[root] = root
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    continue
                out[alias.asname or alias.name] = f"{module}.{alias.name}" if module else alias.name
    return out


def _literal_constants(tree: ast.Module) -> tuple[dict[str, ast.stmt], dict[str, object]]:
    nodes: dict[str, ast.stmt] = {}
    counts: dict[str, int] = {}
    for stmt in tree.body:
        for name in _bound_names(stmt):
            counts[name] = counts.get(name, 0) + 1
        if canonical._is_literal_constant(stmt):
            nodes[canonical._const_name(stmt)] = stmt
    nodes = {k: v for k, v in nodes.items() if counts.get(k) == 1}
    values = {k: ast.literal_eval(v.value) for k, v in nodes.items()}
    return nodes, values


def _bound_names(stmt: ast.stmt) -> set[str]:
    if isinstance(stmt, (*FUNC_TYPES, ast.ClassDef)):
        return {stmt.name}
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return set(import_bindings([stmt]))
    return {
        n.id for n in ast.walk(stmt) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }


def local_names(func: ast.FunctionDef) -> set[str]:
    """Names bound inside `func` (one flat scope, like the canonicalizer), minus
    imports and `global`/`nonlocal` names. Never raises; `self`/`cls` are locals."""
    bound = {a.arg for a in canonical._arg_nodes(func.args)}
    imported: set[str] = set()
    declared: set[str] = set()
    for stmt in func.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.arg):
                bound.add(node.arg)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                bound.add(node.id)
            elif isinstance(node, (*FUNC_TYPES, ast.ClassDef)):
                bound.add(node.name)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.add(node.name)
            elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                bound.add(node.name)
            elif isinstance(node, ast.MatchMapping) and node.rest:
                bound.add(node.rest)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imported.update(import_bindings([node]))
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                declared.update(node.names)
    return bound - imported - declared


def _referenced_names(func: ast.FunctionDef) -> set[str]:
    return {n.id for n in ast.walk(func) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def build_unit(tree: ast.Module, func: ast.FunctionDef) -> Unit:
    """The unit of `func`, a function node somewhere in `tree`."""
    top_funcs = {s.name: s for s in tree.body if isinstance(s, FUNC_TYPES)}
    const_nodes, const_values = _literal_constants(tree)
    module_imports = import_bindings([s for s in tree.body if isinstance(s, (ast.Import, ast.ImportFrom))])
    top_level_names = set()
    for stmt in tree.body:
        top_level_names |= _bound_names(stmt)

    selected = [func]
    todo = [func]
    seen = {id(func)}
    while todo:
        current = todo.pop()
        local = local_names(current)
        for name in sorted(_referenced_names(current) - local):
            target = top_funcs.get(name)
            if target is not None and id(target) not in seen:
                seen.add(id(target))
                selected.append(target)
                todo.append(target)
    helpers = sorted((f for f in selected if f is not func), key=lambda f: f.lineno)

    used: set[str] = set()
    inner_imports: list[ast.stmt] = []
    for f in [func, *helpers]:
        used |= _referenced_names(f) - local_names(f)
        inner_imports += [n for n in ast.walk(f) if isinstance(n, (ast.Import, ast.ImportFrom))]
    constants = {k: const_values[k] for k in const_nodes if k in used}
    imports = {k: v for k, v in module_imports.items() if k in used}
    imports.update(import_bindings(inner_imports))

    unit = Unit(
        func=func,
        helpers=helpers,
        constants=constants,
        constant_nodes={k: const_nodes[k] for k in constants},
        file_constants=const_values,
        imports=imports,
        file_names=top_level_names,
    )
    defined = top_level_names | set(dir(builtins)) | set(imports)
    for f in unit.functions:
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                if name not in unit.locals_of(f) and name not in defined:
                    unit.undefined_calls.add(name)
    return unit


def build_unit_from_source(source: str, name: str) -> Unit:
    """Unit of the top-level function `name` in `source` (used for patterns)."""
    tree = ast.parse(source)
    for stmt in tree.body:
        if isinstance(stmt, FUNC_TYPES) and stmt.name == name:
            return build_unit(tree, stmt)
    raise KeyError(name)


# --------------------------------------------------------------------------- #
# Facts extracted from a unit
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Fact:
    key: str  # comparison key (see name_key)
    display: str  # as written (resolved spelling)
    line: int
    func: str  # owning function's real name


def calls(unit: Unit) -> list[Fact]:
    """Calls to anything but locals and unit functions, excluding `raise X(...)` targets."""
    out = []
    for f in unit.functions:
        raised = {
            id(n.exc) for n in ast.walk(f) if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
        }
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and id(node) not in raised:
                dotted = unit.resolve(node.func, f)
                if dotted is None or dotted.startswith(("fn:", "const:")):
                    continue
                out.append(Fact(name_key(dotted), dotted, node.lineno, f.name))
    return sorted(out, key=lambda x: (x.line, x.key))


def handler_types(handler: ast.ExceptHandler, unit: Unit, func: ast.FunctionDef) -> list[str]:
    """Resolved exception names of one handler; [] for a bare `except:`."""
    if handler.type is None:
        return []
    items = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    out = []
    for item in items:
        dotted = unit.resolve(item, func)
        out.append(dotted if dotted is not None else ast.unparse(item))
    return out


def handlers(unit: Unit) -> list[tuple[ast.ExceptHandler, list[str], ast.FunctionDef]]:
    out = []
    for f in unit.functions:
        for node in ast.walk(f):
            if isinstance(node, ast.ExceptHandler):
                out.append((node, handler_types(node, unit, f), f))
    return sorted(out, key=lambda x: x[0].lineno)


def is_broad(handler: ast.ExceptHandler, types: list[str]) -> bool:
    return handler.type is None or any(t in BROAD_EXCEPTIONS for t in types)


def _builtin_exception(name: str):
    obj = getattr(builtins, name, None)
    return obj if isinstance(obj, type) and issubclass(obj, BaseException) else None


def catches(types: list[str], handler: ast.ExceptHandler, wanted: str) -> bool:
    """True if a handler with `types` catches exception `wanted` (by name)."""
    if is_broad(handler, types):
        return True
    want_key = name_key(wanted)
    for t in types:
        if name_key(t) == want_key:
            return True
        sub, sup = _builtin_exception(wanted), _builtin_exception(t)
        if sub is not None and sup is not None and issubclass(sub, sup):
            return True
    return False


def raises(unit: Unit) -> list[tuple[ast.Raise, str, ast.FunctionDef]]:
    """(raise node, resolved type or "<reraise>", owning function)."""
    out = []
    for f in unit.functions:
        for node in ast.walk(f):
            if isinstance(node, ast.Raise):
                if node.exc is None:
                    kind = "<reraise>"
                else:
                    target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                    kind = unit.resolve(target, f) or "<value>"
                out.append((node, kind, f))
    return sorted(out, key=lambda x: x[0].lineno)


def imported_modules(unit: Unit) -> dict[str, str]:
    """bound name -> origin for every import the unit uses or contains."""
    return dict(unit.imports)


def anonymize(node: ast.AST, unit: Unit, func: ast.FunctionDef) -> ast.AST:
    """Copy of `node` with locals -> `_v`, unit functions -> `_f`, constants -> `_c`,
    import-bound names -> their origin, and annotations and docstrings removed."""
    clone = copy.deepcopy(node)
    locals_ = unit.locals_of(func)
    helpers = unit.helper_names | {unit.func.name}

    class _Anon(ast.NodeTransformer):
        def visit_Name(self, n: ast.Name):  # noqa: N802
            if n.id in locals_:
                n.id = "_v"
            elif n.id in helpers:
                n.id = "_f"
            elif n.id in unit.constant_nodes:
                n.id = "_c"
            elif n.id in unit.imports:
                n.id = unit.imports[n.id]
            return n

        def visit_arg(self, n: ast.arg):  # noqa: N802
            n.arg = "_v"
            n.annotation = None
            return n

        def visit_FunctionDef(self, n):  # noqa: N802
            n.name = "_f"
            n.returns = None
            n.decorator_list = []
            while n.body and canonical._is_string_expr(n.body[0]):
                n.body.pop(0)
            if not n.body:
                n.body.append(ast.Pass())
            self.generic_visit(n)
            return n

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_AnnAssign(self, n: ast.AnnAssign):  # noqa: N802
            self.generic_visit(n)
            if n.value is None:
                return ast.Pass()
            return ast.Assign(targets=[n.target], value=n.value, lineno=n.lineno)

        def visit_ExceptHandler(self, n: ast.ExceptHandler):  # noqa: N802
            if n.name:
                n.name = "_v"
            self.generic_visit(n)
            return n

        def visit_alias(self, n: ast.alias):  # noqa: N802
            return n

    return _Anon().visit(clone)
