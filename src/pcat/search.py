"""Search the catalog with BM25 over pattern metadata (standard library only).

Each active pattern is one document made of its id tokens, title, summary,
category, keywords, use_when, entry point and export names (all read from
catalog/index.json). Requests and documents go through the same deterministic
tokenizer. Results scoring below MATCH_THRESHOLD count as "no reviewed pattern
fits"; the threshold is calibrated on the v3 development set only (see
DECISIONS.md and experiments/mcp/).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Calibrated in v3 Part D on the development set only (scripts/mcp_eval.py retrieval).
MATCH_THRESHOLD = 9.08  # dev-set midpoint between 5.76 (best negative) and 12.41 (worst positive)

BM25_K1 = 1.5
BM25_B = 0.75

STOP_WORDS = frozenset(
    """a an and are as at be but by can do does for from give how i if in into is it its
    me my need of on or our out please should so some that the their them then there these
    this to up us use using want we what when which while will with without write you your
    function python code helper implement make create""".split()
)
# Ordered suffix rules: (suffix, replacement). The first rule that leaves a stem of
# at least 3 characters is applied once. Deliberately light and predictable.
_SUFFIXES = (
    ("ations", ""), ("ation", ""), ("ating", ""), ("ated", ""), ("ates", ""), ("ate", ""),
    ("ies", "y"), ("ing", ""), ("ers", ""), ("er", ""), ("ed", ""), ("es", ""), ("s", ""),
)
_SPLIT = re.compile(r"[^a-z0-9]+")


def stem(word: str) -> str:
    if word.endswith("ss"):
        return word
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) + len(replacement) >= 3:
            return word[: len(word) - len(suffix)] + replacement
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase, split on anything not a-z/0-9 (so `_` and `.` split), drop stop words, stem."""
    return [stem(w) for w in _SPLIT.split(text.lower()) if w and w not in STOP_WORDS]


def document_text(entry: dict) -> str:
    """The searchable text of one index entry."""
    parts = [
        entry["id"],
        entry.get("title") or "",
        entry.get("summary") or "",
        entry.get("category") or "",
        " ".join(entry.get("keywords") or []),
        entry.get("use_when") or "",
        entry.get("entry_point") or "",
        " ".join(entry.get("exports") or []),
    ]
    return " ".join(parts)


@dataclass(frozen=True)
class Hit:
    id: str
    version: int
    score: float
    entry: dict


class SearchIndex:
    """BM25 over index.json entries."""

    def __init__(self, entries: list[dict], include_deprecated: bool = False):
        self.entries = sorted(
            (e for e in entries if include_deprecated or e.get("status") == "active"),
            key=lambda e: (e["id"], e["version"]),
        )
        self.docs = [Counter(tokenize(document_text(e))) for e in self.entries]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log((n - f + 0.5) / (f + 0.5) + 1.0) for t, f in df.items()}

    @classmethod
    def from_root(cls, root: Path, include_deprecated: bool = False) -> "SearchIndex":
        from pcat import catalog as cat

        return cls(cat.read_index(root)["patterns"], include_deprecated)

    def rank(self, request: str) -> list[Hit]:
        """Every pattern with a positive score, best first (ties by id, then version)."""
        terms = sorted(set(tokenize(request)))
        hits = []
        for entry, doc, length in zip(self.entries, self.docs, self.lengths):
            score = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    norm = BM25_K1 * (1 - BM25_B + BM25_B * length / self.avg_length)
                    score += self.idf[term] * tf * (BM25_K1 + 1) / (tf + norm)
            if score > 0:
                hits.append(Hit(entry["id"], entry["version"], round(score, 6), entry))
        hits.sort(key=lambda h: (-h.score, h.id, h.version))
        return hits

    def search(self, request: str, limit: int = 5, threshold: float | None = None) -> list[Hit]:
        """Hits at or above the threshold (MATCH_THRESHOLD by default), at most `limit`."""
        cutoff = MATCH_THRESHOLD if threshold is None else threshold
        return [h for h in self.rank(request) if h.score >= cutoff][: max(limit, 0)]
