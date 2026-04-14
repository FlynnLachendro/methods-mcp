# Using methods-mcp from Claude Code

This is the path the WWSF Loom demos: install the server, point Claude Code at it, ask a science question.

## 1. Install

```bash
uv add methods-mcp                # in any uv-managed project
# or globally:
uv tool install methods-mcp
```

## 2. Tell Claude Code about the server

In a Claude Code session:

```
/mcp add methods-mcp methods-mcp
```

(Form: `/mcp add <name> <command>`. The second `methods-mcp` is the console-script binary, which lives on your PATH after `uv tool install` or inside any project that ran `uv add methods-mcp` + `uv sync`.)

Set your Anthropic key (used for the LLM-driven extraction tools):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# Optional, raises GitHub API rate limit for repro assessment:
export GITHUB_TOKEN=ghp_...
```

## 3. Ask Claude Code a question that uses the tools

Try one of these:

> Take https://arxiv.org/abs/2509.06917 and run methods_repro_review. Summarise what the paper does, the methods steps, and how reproducible the repo looks.

> Compare the reproducibility of the code repos for these three papers: <url1>, <url2>, <url3>. Which has the strongest reproducibility signals?

> Pull the structured methods from this protocol paper [URL] and turn it into a checklist I could hand to a colleague.

Watch the tool calls fire in the Claude Code panel — that's the demo.

## 4. Tools exposed

| Tool | What it does |
|---|---|
| `health` | Liveness + config check. |
| `get_paper_metadata` | Resolve URL/ID/DOI to canonical metadata. |
| `fetch_paper_text` | Best-effort full text + section split. |
| `extract_methods` | LLM + Pydantic structured methods extraction. |
| `find_code_repo` | Discover the paper's GitHub repo. |
| `assess_repo_reproducibility` | No-clone heuristic repro assessment. |
| `summarize_paper` | Three modes: abstract / tldr / exec. |
| `methods_repro_review` | Composite: metadata + methods + repo + repro in one call. |
