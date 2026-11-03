"""Check a pattern's reviewed guards on a code unit (v4 Part B). Standard library only.

Guards are declared per pattern in `pattern.yaml` (`schema.Guard`) and apply to
one pattern function (default: the entry point). They are checked on the unit
of the corresponding function in the user's code (the function plus same-file
helpers it calls), so moving a check into a helper still satisfies a guard.
Messages use the user's names; `names` maps pattern names to them.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass

from pcat import codeunit
from pcat.codeunit import Unit, name_key
from pcat.schema import Guard, PatternMeta


@dataclass(frozen=True)
class GuardResult:
    index: int  # position of the guard in pattern.yaml
    kind: str
    item: str  # the exception, call, module or target the result is about
    ok: bool
    message: str
    line: int
    found: bool = True  # min/max_value: False when the target does not exist in the code


def applicable(meta: PatternMeta, function: str) -> list[tuple[int, Guard]]:
    """Guards of `meta` that apply to pattern function `function`."""
    return [(i, g) for i, g in enumerate(meta.guards) if (g.function or meta.entry_point) == function]


def check(unit: Unit, guards: list[tuple[int, Guard]], names: Mapping[str, str] | None = None) -> list[GuardResult]:
    names = names or {}
    out: list[GuardResult] = []
    fname = unit.func.name
    for index, guard in guards:
        why = f" ({guard.reason})" if guard.reason else ""
        if guard.kind == "must_catch":
            hs = codeunit.handlers(unit)
            for exc in guard.names:
                ok = any(codeunit.catches(types, h, exc) for h, types, _ in hs)
                line = _related_handler_line(hs, exc) or unit.func.lineno
                now = _handler_summary(hs)
                out.append(GuardResult(index, guard.kind, exc, ok,
                                       f"`{fname}` no longer handles `{exc}`{now}; the reviewed "
                                       f"pattern must catch it{why}", line))
        elif guard.kind == "must_call":
            facts = codeunit.calls(unit)
            for call in guard.names:
                ok = any(f.key == name_key(call) for f in facts)
                out.append(GuardResult(index, guard.kind, call, ok,
                                       f"`{fname}` no longer calls `{call}`, which the reviewed "
                                       f"pattern requires{why}", unit.func.lineno))
        elif guard.kind == "must_not_call":
            facts = codeunit.calls(unit)
            for call in guard.names:
                bad = [f for f in facts if f.key == name_key(call)]
                out.append(GuardResult(index, guard.kind, call, not bad,
                                       f"`{bad[0].func if bad else fname}` calls `{bad[0].display if bad else call}`, "
                                       f"which the reviewed pattern forbids{why}",
                                       bad[0].line if bad else unit.func.lineno))
        elif guard.kind == "must_not_import":
            for module in guard.names:
                bad = sorted(b for b, origin in unit.imports.items()
                             if origin == module or origin.startswith(module + "."))
                shown = ", ".join(f"`{unit.imports[b]}`" for b in bad)
                out.append(GuardResult(index, guard.kind, module, not bad,
                                       f"`{fname}` uses {shown or module}, an import the reviewed "
                                       f"pattern forbids{why}", unit.func.lineno))
        elif guard.kind == "must_raise":
            raised = {name_key(kind) for _, kind, _ in codeunit.raises(unit)}
            for exc in guard.names:
                ok = name_key(exc) in raised
                out.append(GuardResult(index, guard.kind, exc, ok,
                                       f"`{fname}` can no longer raise `{exc}`; the reviewed "
                                       f"pattern raises it for invalid input{why}", unit.func.lineno))
        else:  # min_value / max_value
            target = names.get(guard.target, guard.target)
            value, line, found = resolve_value(unit, target)
            if value is None:
                out.append(GuardResult(index, guard.kind, guard.target, True,
                                       f"`{target}` not found in `{fname}`; guard not checked", line, found))
                continue
            low = guard.kind == "min_value"
            ok = value >= guard.value if low else value <= guard.value
            label = f"`{target}`" + (f" (pattern: `{guard.target}`)" if target != guard.target else "")
            word = "below the reviewed minimum" if low else "above the reviewed maximum"
            out.append(GuardResult(index, guard.kind, guard.target, ok,
                                   f"{label} is {_fmt(value)}, {word} {_fmt(guard.value)}{why}", line))
    return out


def violations(results: list[GuardResult]) -> list[GuardResult]:
    return [r for r in results if not r.ok]


def resolve_value(unit: Unit, target: str) -> tuple[float | None, int, bool]:
    """Numeric value of parameter `target`'s default or module constant `target`."""
    args = unit.func.args
    positional = [*args.posonlyargs, *args.args]
    defaults = dict(zip([a.arg for a in positional[len(positional) - len(args.defaults):]], args.defaults))
    defaults.update({a.arg: d for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None})
    all_args = {a.arg for a in [*positional, *args.kwonlyargs]}
    if target in all_args:
        node = defaults.get(target)
        if node is None:
            return None, unit.func.lineno, False
        if isinstance(node, ast.Name) and node.id in unit.file_constants:
            return _number(unit.file_constants[node.id]), node.lineno, True
        try:
            return _number(ast.literal_eval(node)), node.lineno, True
        except (ValueError, TypeError, SyntaxError):
            return None, node.lineno, False
    if target in unit.file_constants:
        line = unit.constant_nodes[target].lineno if target in unit.constant_nodes else unit.func.lineno
        return _number(unit.file_constants[target]), line, True
    return None, unit.func.lineno, False


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _fmt(value) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _related_handler_line(hs, exc: str) -> int | None:
    root = exc.split(".")[0]
    for h, types, _ in hs:
        if any(t.split(".")[0] == root for t in types):
            return h.lineno
    return hs[0][0].lineno if hs else None


def _handler_summary(hs) -> str:
    if not hs:
        return " (it has no `except`)"
    shown = []
    for h, types, _ in hs:
        text = "bare except" if h.type is None else ", ".join(types)
        if text not in shown:
            shown.append(text)
    return f" (it catches {'; '.join(shown)})"
