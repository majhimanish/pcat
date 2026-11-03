"""The real MCP server through the SDK's in-memory client (skips without the mcp extra)."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("mcp")
import anyio  # noqa: E402
from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402

from conftest import REPO_ROOT  # noqa: E402
from pcat.mcp_server import build_server  # noqa: E402
from pcat.serving import CatalogService  # noqa: E402


def call(tool, arguments, log=None):
    server = build_server(CatalogService(REPO_ROOT, log))

    async def run():
        async with create_connected_server_and_client_session(server._mcp_server) as client:
            init = await client.initialize()
            tools = await client.list_tools()
            result = await client.call_tool(tool, arguments)
            return init, tools, result

    return anyio.run(run)


def payload(result):
    return json.loads(result.content[0].text)


def test_initialize_sends_instructions_and_lists_three_tools():
    init, tools, _ = call("search_patterns", {"request": "hash a password"})
    assert "search_patterns" in init.instructions and "auth:" in init.instructions
    assert sorted(t.name for t in tools.tools) == ["check_code", "get_pattern", "search_patterns"]


def test_search_and_get_pattern_over_mcp(tmp_path):
    _, _, found = call("search_patterns", {"request": "store and verify user passwords"})
    assert not found.isError and payload(found)["matches"][0]["id"] == "auth.password.pbkdf2"
    _, _, got = call("get_pattern", {"id": "auth.password.pbkdf2", "names": {"f0": "make_hash"}},
                     log=tmp_path / "log.jsonl")
    assert not got.isError and "def make_hash(" in payload(got)["code"]
    assert json.loads((tmp_path / "log.jsonl").read_text().splitlines()[0])["tool"] == "get_pattern"


def test_errors_become_tool_errors():
    _, _, bad = call("get_pattern", {"id": "auth.password.pbkdf2", "names": {"nope": "x"}})
    assert bad.isError and "invalid name keys" in bad.content[0].text
    _, _, unknown = call("get_pattern", {"id": "no.such.pattern"})
    assert unknown.isError and "unknown pattern id" in unknown.content[0].text


def test_check_code_over_mcp():
    _, _, result = call("check_code", {"code": "def f(:\n"})
    assert not result.isError and payload(result)["error"].startswith("syntax error")


def test_pcat_serve_over_stdio_from_another_directory(tmp_path):
    """The way MCP clients run it: a subprocess started outside the repository."""
    import sys

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    log = tmp_path / "calls.jsonl"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pcat.cli", "serve", "--catalog", str(REPO_ROOT / "catalog"), "--log", str(log)],
        cwd=str(tmp_path),
    )

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                result = await session.call_tool("search_patterns", {"request": "rate limit API requests per client with a token bucket"})
                return init, result

    init, result = anyio.run(run)
    assert init.serverInfo.name == "pcat"
    assert payload(result)["matches"][0]["id"] == "ratelimit.token_bucket.check"
    assert json.loads(log.read_text().splitlines()[0])["tool"] == "search_patterns"
