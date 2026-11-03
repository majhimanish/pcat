"""`pcat serve`: the catalog tools over MCP (stdio). Requires the `mcp` extra.

The tool logic lives in pcat.serving (no MCP dependency); this module only
registers it with the official MCP Python SDK.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from pcat.errors import PcatError
from pcat.serving import CatalogService

SERVER_NAME = "pcat"


def build_server(service: CatalogService) -> FastMCP:
    server = FastMCP(SERVER_NAME, instructions=service.instructions())

    @server.tool()
    def search_patterns(request: str, limit: int = 5) -> dict[str, Any]:
        """Find reviewed code patterns for a plain-language request.

        Returns matches above the relevance threshold (id, title, summary, use_when,
        score, requires, exports). An empty list means no reviewed pattern fits.
        """
        try:
            return service.search_patterns(request, limit)
        except PcatError as exc:
            raise ToolError(str(exc)) from None

    @server.tool()
    def get_pattern(id: str, names: dict[str, str] | None = None) -> dict[str, Any]:
        """Get a reviewed pattern's code, rendered with your names.

        `names` maps placeholders (see the returned `names`: f0 = entry point,
        v0.. = its parameters/locals, fN.vM = helper locals, cN = constants) to
        the identifiers you want. Also returns requires, exports, usage, version
        and status (with a warning if the pattern is deprecated).
        """
        try:
            return service.get_pattern(id, names)
        except PcatError as exc:
            raise ToolError(str(exc)) from None

    @server.tool()
    def check_code(code: str) -> dict[str, Any]:
        """Check Python code against the catalog.

        For each function: covered (exact match with a reviewed pattern), near
        (same structure, only literal values differ) or none.
        """
        return service.check_code(code)

    return server


def serve(root: Path, log_path: Path | None = None) -> None:
    build_server(CatalogService(root, log_path)).run("stdio")
