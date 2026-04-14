"""Smoke tests: instantiate the FastMCP server and confirm tool registration."""

from __future__ import annotations

import pytest

from methods_mcp.server import mcp


@pytest.mark.asyncio
async def test_server_registers_expected_tools() -> None:
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "health",
        "get_paper_metadata",
        "fetch_paper_text",
        "extract_methods",
        "find_code_repo",
        "assess_repo_reproducibility",
        "summarize_paper",
        "methods_repro_review",
    }
    assert expected.issubset(names), f"missing: {expected - names}"


@pytest.mark.asyncio
async def test_health_tool_runs() -> None:
    health_tool = await mcp.get_tool("health")
    result = await health_tool.run(arguments={})
    assert result is not None
