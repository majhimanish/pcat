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

v5.1: every unit has a symbol table. Besides imports (any alias) it knows the
file's own top-level definitions (classes, functions, non-literal assignments),
which resolve to `<module>.<name>` when the file's module path is known
(`lnbits/decorators.py` -> `lnbits.decorators.KeyChecker`), so a class defined
in the same file and the same class imported elsewhere resolve identically.
Names the unit uses that nothing binds (a snippet without its imports) are
*unknown*; `deviation.bind` may assume them to be what the pattern means by the
same name, and rules that would depend on the rest are skipped, never reported.
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
    module: str | None = None  # dotted module path of the file, when known
    file_defs: set[str] = field(default_factory=set)  # top-level names that are not imports/literal constants
    unknown: set[str] = field(default_factory=set)  # names the unit uses that nothing binds
    bound: dict[str, str] = field(default_factory=dict)  # assumed bindings (deviation.bind): name -> origin
    bound_imports: set[str] = field(default_factory=set)  # those of `bound` that are imports on the other side
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
        assumed bindings and import-bound names -> their origin; other same-file
        definitions -> `<module>.<name>` (bare without a module path); builtins and
        unknown names stay as they are; attribute chains on anything else -> ".attr".
        """
        if isinstance(expr, ast.Name):
            name = expr.id
            if name in self.locals_of(func):
                return None
            if name in self.helper_names or name == self.func.name:
                return f"fn:{name}"
            if name in self.constant_nodes:
                return f"const:{name}"
            return self.global_name(name)
        if isinstance(expr, ast.Attribute):
            base = self.resolve(expr.value, func) if isinstance(expr.value, (ast.Name, ast.Attribute)) else None
            if base is None or base.startswith((".", "fn:", "const:")):
                return f".{expr.attr}"
            return f"{base}.{expr.attr}"
        return None

    def global_name(self, name: str) -> str:
        """Resolution of a module-level name (not a local, helper or literal constant)."""
        if name in self.bound:
            return self.bound[name]
        if name in self.imports:
            return self.imports[name]
        if name in self.file_defs:
            return self.qualify(name)
        return name

    def qualify(self, name: str) -> str:
        return f"{self.module}.{name}" if self.module else name

    def spell(self, dotted: str) -> str:
        """`dotted` as written in this file: same-file definitions lose the module prefix."""
        if self.module and dotted.startswith(self.module + "."):
            rest = dotted[len(self.module) + 1:]
            if rest.split(".")[0] in self.file_defs:
                return rest
        return dotted

    @property
    def unresolved(self) -> set[str]:
        """Unknown names that no assumed binding covers."""
        return self.unknown - set(self.bound)

    def is_unresolved(self, dotted: str | None) -> bool:
        return bool(dotted) and dotted.split(".")[0] in self.unresolved

    @property
    def resolution(self) -> str:
        return "partial" if self.unknown else "full"


def last_segment(dotted: str) -> str:
    return dotted.rsplit(".", 1)[-1]


def target_matches(target: str, dotted: str | None, unit: Unit | None = None, *, strict: bool = False) -> bool:
    """Does resolved name `dotted` refer to guard/pattern name `target`?

    Qualified targets compare by `name_key` (any alias of the import, or the
    same-file definition in that module). An unqualified target (`KeyChecker`)
    matches a same-file definition or builtin of that name and, unless `strict`
    (used for `must_not_call`), any import whose last segment it is."""
    if not dotted or dotted.startswith(("fn:", "const:")):
        return False
    if name_key(target) == name_key(dotted):
        return True
    if target.startswith("."):  # a method on any value: any attribute call with that name
        return "." in dotted and last_segment(dotted) == target[1:]
    if "." in target or dotted.startswith("."):
        return False
    if last_segment(dotted) != target:
        return False
    if not strict:
        return True
    return unit is not None and unit.spell(dotted) == target


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


def _module_level_statements(tree: ast.Module) -> list[ast.stmt]:
    """Top-level statements plus those nested in top-level `if`/`try`/`with` blocks
    (`if TYPE_CHECKING:` and `try: import x except ImportError:` imports)."""
    out: list[ast.stmt] = []

    def walk(body: list[ast.stmt]) -> None:
        for stmt in body:
            out.append(stmt)
            if isinstance(stmt, ast.If):
                walk(stmt.body)
                walk(stmt.orelse)
            elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                walk(stmt.body)
                for h in stmt.handlers:
                    walk(h.body)
                walk(stmt.orelse)
                walk(stmt.finalbody)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                walk(stmt.body)

    walk(tree.body)
    return out


def module_for_path(path) -> str | None:
    """Dotted module path of a `.py` file: its name plus every enclosing folder that
    has an `__init__.py` (`lnbits/decorators.py` -> `lnbits.decorators`)."""
    from pathlib import Path

    path = Path(path)
    if path.suffix != ".py":
        return None
    parts = [] if path.stem == "__init__" else [path.stem]
    folder = path.parent
    while (folder / "__init__.py").is_file() and folder.name:
        parts.insert(0, folder.name)
        if folder.parent == folder:
            break
        folder = folder.parent
    name = ".".join(parts)
    if not (name and all(p.isidentifier() for p in parts)):
        return None
    # v6: namespace packages (folders without __init__.py) and src/ layouts. Take the path
    # from the project's source root (the folder with pyproject.toml / setup.py / setup.cfg
    # / .git, or its src/); use it when it extends the __init__.py chain.
    longer = _from_source_root(path)
    if longer and len(longer) > len(parts) and longer[-len(parts):] == parts:
        return ".".join(longer)
    return name


PROJECT_FILES = ("pyproject.toml", "setup.py", "setup.cfg", ".git")


def _from_source_root(path) -> list[str] | None:
    path = path.resolve()
    for folder in path.parents:
        if any((folder / f).exists() for f in PROJECT_FILES):
            base = folder / "src" if (folder / "src") in path.parents else folder
            rel = path.relative_to(base).with_suffix("").parts
            rel = list(rel[:-1]) if rel and rel[-1] == "__init__" else list(rel)
            return rel if rel and all(p.isidentifier() for p in rel) else None
    return None


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


def build_unit(tree: ast.Module, func: ast.FunctionDef, module: str | None = None,
               context: ast.Module | None = None) -> Unit:
    """The unit of `func`, a function node somewhere in `tree`.

    `module`: the file's dotted module path, when known. `context`: the
    surrounding file (or just its imports) when `tree` is a fragment of it; its
    imports and top-level definitions are added to the symbol table."""
    if context is not None:  # the surrounding file: its definitions, minus those `tree` redefines
        own = set().union(*(_bound_names(s) for s in tree.body)) if tree.body else set()
        tree = ast.Module(body=[s for s in context.body if not (_bound_names(s) & own)] + tree.body,
                          type_ignores=[])
    top_funcs = {s.name: s for s in tree.body if isinstance(s, FUNC_TYPES)}
    const_nodes, const_values = _literal_constants(tree)
    module_imports = import_bindings(
        [s for s in _module_level_statements(tree) if isinstance(s, (ast.Import, ast.ImportFrom))])
    top_level_names = set()
    for stmt in tree.body:
        top_level_names |= _bound_names(stmt)
    file_defs = top_level_names - set(module_imports) - set(const_nodes)

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
        module=module,
        file_defs=file_defs,
    )
    defined = top_level_names | set(dir(builtins)) | set(imports)
    for f in unit.functions:
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                if name not in unit.locals_of(f) and name not in defined:
                    unit.undefined_calls.add(name)
    known = defined | unit.helper_names | {func.name} | set(const_nodes)
    for f in unit.functions:
        for name in _referenced_names(f) - unit.locals_of(f):
            if name not in known and not canonical._is_dunder(name):
                unit.unknown.add(name)
    return unit


def build_unit_from_source(source: str, name: str, module: str | None = None) -> Unit:
    """Unit of the top-level function `name` in `source` (used for patterns)."""
    tree = ast.parse(source)
    for stmt in tree.body:
        if isinstance(stmt, FUNC_TYPES) and stmt.name == name:
            return build_unit(tree, stmt, module)
    raise KeyError(name)


# --------------------------------------------------------------------------- #
# Facts extracted from a unit
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Fact:
    key: str  # comparison key (see name_key)
    display: str  # as written (resolved spelling; same-file definitions without the module)
    line: int
    func: str  # owning function's real name
    dotted: str = ""  # full resolution
    alternatives: tuple[str, ...] = ()  # v5.1: `(conn or db).execute` -> ("<db origin>.execute",)


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
                out.append(Fact(name_key(dotted), unit.spell(dotted), node.lineno, f.name, dotted,
                                _alternatives(node.func, unit, f)))
    return sorted(out, key=lambda x: (x.line, x.key))


def _alternatives(func_expr: ast.expr, unit: Unit, func: ast.FunctionDef) -> tuple[str, ...]:
    """For a method call on `a or b` / `a if c else b`, the resolved `a.m`, `b.m` (named
    operands only): the call is a call on one of them."""
    if not isinstance(func_expr, ast.Attribute):
        return ()
    base = func_expr.value
    operands = base.values if isinstance(base, ast.BoolOp) else (
        [base.body, base.orelse] if isinstance(base, ast.IfExp) else [])
    out = []
    for operand in operands:
        if isinstance(operand, (ast.Name, ast.Attribute)):
            r = unit.resolve(operand, func)
            if r is not None and not r.startswith((".", "fn:", "const:")):
                out.append(f"{r}.{func_expr.attr}")
    return tuple(sorted(set(out)))


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


def catches(types: list[str], handler: ast.ExceptHandler, wanted: str, guard: bool = False) -> bool:
    """True if a handler with `types` catches exception `wanted` (by name). `guard`:
    `wanted` is a guard target (an unqualified one matches by last segment, see
    `target_matches`); otherwise both sides are resolved names (`name_key`)."""
    if is_broad(handler, types):
        return True
    for t in types:
        if target_matches(wanted, t) if guard else name_key(t) == name_key(wanted):
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
            else:
                n.id = unit.global_name(n.id)
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
