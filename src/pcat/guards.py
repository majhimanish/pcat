"""Check a pattern's reviewed guards on a code unit (v4 Part B). Standard library only.

Guards are declared per pattern in `pattern.yaml` (`schema.Guard`) and apply to
one pattern function (default: the entry point). They are checked on the unit
of the corresponding function in the user's code (the function plus same-file
helpers it calls), so moving a check into a helper still satisfies a guard.
Messages use the user's names; `names` maps pattern names to them.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass

from pcat import codeunit
from pcat.codeunit import Unit, last_segment, target_matches
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
    skipped: bool = False  # v5.1: not checked because the code uses an unresolved name that may be it


def applicable(meta: PatternMeta, function: str) -> list[tuple[int, Guard]]:
    """Guards of `meta` that apply to pattern function `function`."""
    return [(i, g) for i, g in enumerate(meta.guards) if (g.function or meta.entry_point) == function]


def check(unit: Unit, guards: list[tuple[int, Guard]], names: Mapping[str, str] | None = None) -> list[GuardResult]:
    names = names or {}
    out: list[GuardResult] = []
    fname = unit.func.name
    for index, guard in guards:
        why = f" ({guard.reason})" if guard.reason else ""
        start = len(out)
        if guard.kind == "must_catch":
            hs = codeunit.handlers(unit)
            for exc in guard.names:
                ok = any(codeunit.catches(types, h, exc, guard=True) for h, types, _ in hs)
                line = _related_handler_line(hs, exc) or unit.func.lineno
                if not ok and _maybe(unit, exc, [t for _, types, _ in hs for t in types]):
                    out.append(_skip(index, guard.kind, exc, fname, line))
                    continue
                now = _handler_summary(hs, unit)
                out.append(GuardResult(index, guard.kind, exc, ok,
                                       f"`{fname}` no longer handles `{exc}`{now}; the reviewed "
                                       f"pattern must catch it{why}", line))
        elif guard.kind == "must_call":
            facts = codeunit.calls(unit)
            for call in guard.names:
                ok = any(target_matches(call, f.dotted, unit) for f in facts)
                if not ok and _maybe(unit, call, [f.dotted for f in facts]):
                    out.append(_skip(index, guard.kind, call, fname, unit.func.lineno))
                    continue
                out.append(GuardResult(index, guard.kind, call, ok,
                                       f"`{fname}` no longer calls `{call}`, which the reviewed "
                                       f"pattern requires{why}", unit.func.lineno))
        elif guard.kind == "must_not_call":
            facts = codeunit.calls(unit)
            for call in guard.names:
                bad = [f for f in facts if target_matches(call, f.dotted, unit, strict=True)]
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
            raised = [kind for _, kind, _ in codeunit.raises(unit)]
            for exc in guard.names:
                ok = any(target_matches(exc, kind, unit) for kind in raised)
                if not ok and _maybe(unit, exc, raised):
                    out.append(_skip(index, guard.kind, exc, fname, unit.func.lineno))
                    continue
                out.append(GuardResult(index, guard.kind, exc, ok,
                                       f"`{fname}` can no longer raise `{exc}`; the reviewed "
                                       f"pattern raises it for invalid input{why}", unit.func.lineno))
        elif guard.kind == "must_include":
            target = names.get(guard.target, guard.target)
            value, line, found = resolve_literal(unit, target)
            if not found:
                out.append(GuardResult(index, guard.kind, guard.target, True,
                                       f"`{target}` not found in `{fname}`; guard not checked", line, False))
                continue
            label = f"`{target}`" + (f" (pattern: `{guard.target}`)" if target != guard.target else "")
            if not isinstance(value, (list, tuple, set, frozenset)):
                out.append(GuardResult(index, guard.kind, guard.target, False,
                                       f"{label} is no longer a collection ({value!r}); the reviewed "
                                       f"pattern requires it to include {_items(guard.values)}{why}", line))
                continue
            missing = [v for v in guard.values if v not in value]
            out.append(GuardResult(index, guard.kind, guard.target, not missing,
                                   f"{label} no longer includes {_items(missing)}; the reviewed pattern "
                                   f"requires {_items(guard.values)}{why}", line))
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
        if guard.match == "any":
            out[start:] = [_any(out[start:], guard, fname, why)]
    return out


ANY_VERBS = {"must_catch": "handles", "must_call": "calls", "must_raise": "can raise"}


def _any(results: list[GuardResult], guard: Guard, fname: str, why: str) -> GuardResult:
    """One result for a `match: any` guard: it holds when one of its names does."""
    item = " | ".join(guard.names)
    hit = next((r for r in results if r.ok and not r.skipped), None)
    if hit is not None:
        return GuardResult(hit.index, guard.kind, item, True, hit.message, hit.line)
    skipped = next((r for r in results if r.skipped), None)
    if skipped is not None:
        return dataclasses.replace(skipped, item=item)
    shown = ", ".join(f"`{n}`" for n in guard.names)
    return GuardResult(results[0].index, guard.kind, item, False,
                       f"`{fname}` no longer {ANY_VERBS[guard.kind]} any of {shown}; the reviewed pattern "
                       f"requires one of them{why}", results[0].line)


def violations(results: list[GuardResult]) -> list[GuardResult]:
    return [r for r in results if not r.ok]


def _maybe(unit: Unit, target: str, resolved: list[str]) -> bool:
    """True if one of `resolved` is an unresolved name that may be `target` (same last segment)."""
    return any(unit.is_unresolved(r) and last_segment(r) == last_segment(target) for r in resolved)


def _skip(index: int, kind: str, item: str, fname: str, line: int) -> GuardResult:
    return GuardResult(index, kind, item, True,
                       f"`{fname}`: guard {kind} `{item}` not checked: the code uses a name that is "
                       f"not imported and may be it (pass the file's imports as context)",
                       line, True, True)


def _items(values) -> str:
    return ", ".join(repr(v) for v in values)


def resolve_value(unit: Unit, target: str) -> tuple[float | None, int, bool]:
    """Numeric value of parameter `target`'s default or module constant `target`."""
    value, line, found = resolve_literal(unit, target)
    number = _number(value) if found else None
    return number, line, found and number is not None


def resolve_literal(unit: Unit, target: str) -> tuple[object, int, bool]:
    """Literal value of parameter `target`'s default or module constant `target`.

    Returns (value, line, found); a default that is not a literal or a file
    constant counts as not found."""
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
            return unit.file_constants[node.id], node.lineno, True
        try:
            return ast.literal_eval(node), node.lineno, True
        except (ValueError, TypeError, SyntaxError):
            return None, node.lineno, False
    if target in unit.file_constants:
        line = unit.constant_nodes[target].lineno if target in unit.constant_nodes else unit.func.lineno
        return unit.file_constants[target], line, True
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


def _handler_summary(hs, unit: Unit | None = None) -> str:
    if not hs:
        return " (it has no `except`)"
    shown = []
    for h, types, _ in hs:
        text = "bare except" if h.type is None else ", ".join(unit.spell(t) if unit else t for t in types)
        if text not in shown:
            shown.append(text)
    return f" (it catches {'; '.join(shown)})"
