"""Similarity of two shape texts (used by inference and pattern-function choice).

Moved here from the v2.1 variance study in v6 so the product package does not depend on
research code; the function is unchanged, so every similarity (and the inference
threshold calibrated on it) is the same.
"""

from __future__ import annotations

import difflib


def similarity(a: str, b: str) -> float:
    """difflib ratio of two shape texts (1.0 = identical)."""
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
