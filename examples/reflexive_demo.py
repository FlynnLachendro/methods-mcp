"""Reflexive Agent SDK demo — methods-mcp consumed by Claude Agent SDK.

Picks a recent "agentic AI-for-science" paper, points the agent at it, and
asks the agent to extract the methods + repro-assess it using ONLY tools
exposed by our methods-mcp server. The "reflexive" framing: an agent
analysing the methods of agentic-scientist papers using a tool another
agent will plausibly use during the WWSF cohort.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    uv run --extra agent python examples/reflexive_demo.py

Or with a custom paper:
    uv run --extra agent python examples/reflexive_demo.py https://arxiv.org/abs/2509.06917
"""

from __future__ import annotations

import asyncio
import os
import sys
from textwrap import shorten

import anyio

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
except ImportError as e:  # pragma: no cover
    raise SystemExit("claude-agent-sdk not installed. Re-run with `uv sync --extra agent`.") from e


DEFAULT_PAPER = "https://arxiv.org/abs/2509.06917"  # Paper2Agent (Stanford)
DEFAULT_PROMPT_TEMPLATE = """You are evaluating a recent AI-for-Science paper using the
methods-mcp tools.

Paper to analyse: {paper}

Do these steps in order, calling the tools yourself — don't ask me first:
  1. methods-mcp get_paper_metadata to confirm what we're looking at.
  2. methods-mcp methods_repro_review to extract the structured methods,
     find the code repo, and assess reproducibility in one go.
  3. Write a tight summary (~150 words) of (a) what the paper does,
     (b) the structured methods steps as a numbered list,
     (c) the reproducibility verdict + score + the recommended entrypoint
     if there is one.

Be specific. Quote concrete signal names from the assessment."""


def _server_command() -> tuple[str, list[str]]:
    """Resolve how to launch our methods-mcp server as an MCP subprocess.

    Prefers the local console script (works once `uv sync` has run); falls
    back to `python -m methods_mcp.server`.
    """
    venv_bin = (
        os.path.join(os.path.dirname(sys.executable), "methods-mcp") if sys.executable else None
    )
    if venv_bin and os.path.exists(venv_bin):
        return venv_bin, []
    return sys.executable, ["-m", "methods_mcp.server"]


async def main() -> None:
    paper = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PAPER
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running this demo.")

    cmd, args = _server_command()
    print(f"== Spawning methods-mcp subprocess: {cmd} {' '.join(args)}")
    print(f"== Target paper: {paper}\n")

    options = ClaudeAgentOptions(
        mcp_servers={
            "methods-mcp": {
                "type": "stdio",
                "command": cmd,
                "args": args,
                "env": {
                    "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
                    **(
                        {"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]}
                        if "GITHUB_TOKEN" in os.environ
                        else {}
                    ),
                },
            }
        },
        allowed_tools=[
            "mcp__methods-mcp__get_paper_metadata",
            "mcp__methods-mcp__methods_repro_review",
            "mcp__methods-mcp__extract_methods",
            "mcp__methods-mcp__find_code_repo",
            "mcp__methods-mcp__assess_repo_reproducibility",
            "mcp__methods-mcp__summarize_paper",
            "mcp__methods-mcp__fetch_paper_text",
            "mcp__methods-mcp__health",
        ],
    )

    prompt = DEFAULT_PROMPT_TEMPLATE.format(paper=paper)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        preview = shorten(str(block.input), 120, placeholder="…")
                        print(f"\n  → tool: {block.name}({preview})")
            elif isinstance(msg, ResultMessage):
                print()
                if msg.usage:
                    print(
                        "\n--- usage:",
                        f"in={msg.usage.get('input_tokens', '?')}",
                        f"out={msg.usage.get('output_tokens', '?')}",
                        f"cost=${msg.total_cost_usd:.4f}" if msg.total_cost_usd else "",
                    )


if __name__ == "__main__":
    anyio.run(main)
    # asyncio fallback (older Python without anyio)
    _ = asyncio
