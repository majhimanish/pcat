"""ASCII slugs for URLs and identifiers."""

import re
import unicodedata


def slugify(text: str, separator: str = "-") -> str:
    """Return `text` as a lowercase ASCII slug.

    Accents are removed via NFKD decomposition; characters with no ASCII
    equivalent are dropped. Every run of other characters becomes one
    `separator`, and separators at the edges are removed.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    return separator.join(words)
