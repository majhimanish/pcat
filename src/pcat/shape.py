"""Shape fingerprints: the canonical form with literal values blanked out.

Two pieces of code have the same *shape* when their canonical forms differ only
in literal values. The miner groups code by shape; the exact (canonical)
fingerprint then tells which members are fully identical.

Rules (SHAPE_VERSION 1), applied to the v1.1 canonical form:

- numbers (int, float, complex) become 0, strings become "", bytes become b""
- True, False, None and ... are kept (they usually change behaviour)
- f-strings keep their structure (expressions, conversions, format specs) but
  their literal text parts are removed
- constants (cN) keep their names; their values are blanked like any literal

This module never changes canonicalization or exact fingerprints; it only
post-processes canonical text. Bump SHAPE_VERSION on any change that can alter
a shape fingerprint (reports record it, and the miner cache is keyed by it).
"""

from __future__ import annotations

import ast

from pcat import canonical

SHAPE_VERSION = 1


class _LiteralBlanker(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.Constant:  # noqa: N802
        value = node.value
        if value is None or value is Ellipsis or isinstance(value, bool):
            return node
        if isinstance(value, (int, float, complex)):
            blank: object = 0
        elif isinstance(value, str):
            blank = ""
        elif isinstance(value, bytes):
            blank = b""
        else:  # pragma: no cover - no other constant types exist
            return node
        return ast.copy_location(ast.Constant(value=blank), node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.JoinedStr:  # noqa: N802
        node.values = [self.visit(v) for v in node.values if not isinstance(v, ast.Constant)]
        return node


def blank_literals(node: ast.AST) -> ast.AST:
    """Blank literal values in `node` in place (and return it)."""
    return _LiteralBlanker().visit(node)


def shape_text_from_canonical(canonical_text: str) -> str:
    """Shape text for already-canonical text."""
    tree = blank_literals(ast.parse(canonical_text))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree).strip("\n") + "\n"


def shape_canonicalize(
    source: str, entry_point: str | None = None, keep_annotations: bool = True
) -> str:
    """Canonicalize `source` (v1.1 rules), then blank its literals."""
    return shape_text_from_canonical(
        canonical.canonicalize(source, entry_point, keep_annotations)
    )


def shape_fingerprint(
    source: str, entry_point: str | None = None, keep_annotations: bool = True
) -> str:
    """SHA-256 of `shape_canonicalize(source, ...)`."""
    return canonical.fingerprint(shape_canonicalize(source, entry_point, keep_annotations))


def node_count(node: ast.AST) -> int:
    """Number of AST nodes in `node`, including itself."""
    return sum(1 for _ in ast.walk(node))
