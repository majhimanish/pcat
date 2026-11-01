"""Exception types shared by all pcat modules."""

from __future__ import annotations


class PcatError(Exception):
    """Base class for every error pcat reports to the user."""


class CanonicalizationError(PcatError):
    """Source code cannot be canonicalized (syntax error or forbidden construct)."""


class RenderError(PcatError):
    """A name map cannot be applied to a canonical form."""


class CatalogError(PcatError):
    """The catalog on disk is missing, malformed or inconsistent."""
