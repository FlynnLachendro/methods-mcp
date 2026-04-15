# methods-mcp

<!-- mcp-name: io.github.FlynnLachendro/methods-mcp -->

[![PyPI](https://img.shields.io/pypi/v/methods-mcp.svg)](https://pypi.org/project/methods-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/methods-mcp.svg)](https://pypi.org/project/methods-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Lightweight, on-demand MCP server for **structured methods extraction** + **reproducibility heuristics** on academic papers. Built for the [Worldwide AI Science Fellowship](https://www.aisciencesummit.com/) build challenge.

> ⚠️ **Status: alpha (0.1.x).** The tool surface and output shapes may shift between minor versions. **Pin to an exact version** in production. Bug reports very welcome via [GitHub Issues](https://github.com/FlynnLachendro/methods-mcp/issues).

## Quick demo

```text
$ uvx --from methods-mcp methods-mcp --version
methods-mcp 0.1.4

# In a Claude Code session:
> /mcp add methods-mcp methods-mcp
> Run methods_repro_review on https://arxiv.org/abs/2509.06917

  → tool: get_paper_metadata({"input_str":"https://arxiv.org/abs/2509.06917"})
  → tool: methods_repro_review({"input_str":"https://arxiv.org/abs/2509.06917"})

# Returns in seconds:
# - methods: 10 steps, 2 reagents, 3 equipment, 4 analyses (confidence 0.72)
# - code_repo: google-deepmind/alphagenome (detected in paper text, confidence 0.9)
# - repro_assessment: likely-reproducible (0.9/1.0)
#   entrypoint: python src/alphagenome/visualization/plot.py
```

---

`methods-mcp` is a small, sharply-scoped [Model Context Protocol](https://modelcontextprotocol.io) server. It gives any AI agent (Claude Code, Claude Desktop, your Agent SDK script, etc.) eight tools that turn an academic paper URL into:

- canonical metadata,
- best-effort full text + section split,
- a **Pydantic-validated structured methods object** (steps / reagents / equipment / analyses),
- the paper's associated **code repository** (best-effort discovery),
- a **no-execution-required reproducibility verdict** for that repo, and
- a multi-mode summary.

The wedge: heavyweight pipelines like [Paper2Agent](https://arxiv.org/abs/2509.06917) (Stanford) take 30 minutes to hours to digest a paper into agent-ready tools. `methods-mcp` is the **agent-callable, on-demand** complement — every tool returns in seconds, no clone, no execution.

---

## Install

```bash
uv add methods-mcp
# or, install globally:
uv tool install methods-mcp
# or, classic pip:
pip install methods-mcp
```

### API keys

For best performance, set **both**:

| Variable | Required? | What you get without it |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Required** for `extract_methods`, `summarize_paper`, `methods_repro_review` | Those tools raise `RuntimeError: ANTHROPIC_API_KEY not set`. Non-LLM tools (`fetch_paper_text`, `find_code_repo`, `assess_repo_reproducibility`) still work fine. |
| `GITHUB_TOKEN` | **Optional but recommended** for `assess_repo_reproducibility` / `methods_repro_review` | You're capped at the GitHub unauthenticated rate limit (**60 req/hr per IP**). Each repo assessment is ~3 calls, so you'll hit the ceiling after ~15–20 repos/hr. With a token: **5,000 req/hr** (effectively unlimited). |

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...          # optional but recommended
```

Neither key is logged or persisted — they're sent only to `api.anthropic.com` and `api.github.com` respectively. See [`SECURITY.md`](SECURITY.md).

## Use it from Claude Code

```
/mcp add methods-mcp methods-mcp
```

Then in any Claude Code chat:

> Take https://arxiv.org/abs/2509.06917 and run `methods_repro_review`. Summarise what the paper does, the methods steps, and how reproducible the repo looks.

See [`examples/claude_code_demo.md`](examples/claude_code_demo.md) for more session prompts.

## Use it from the Claude Agent SDK

```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

options = ClaudeAgentOptions(
    mcp_servers={
        "methods-mcp": {
            "type": "stdio",
            "command": "methods-mcp",
            "args": [],
        }
    },
    allowed_tools=["mcp__methods-mcp__methods_repro_review"],
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(
        "Run methods_repro_review on https://arxiv.org/abs/2509.06917 "
        "and tell me whether the repo looks reproducible."
    )
    async for msg in client.receive_response():
        print(msg)
```

A complete runnable example lives in [`examples/reflexive_demo.py`](examples/reflexive_demo.py).

## Tools

| Tool | What it does |
|---|---|
| `health` | Server liveness + config check. |
| `get_paper_metadata(input_str)` | Resolve URL / arXiv ID / DOI to canonical metadata. arXiv inputs hit the arXiv export API for title/authors/abstract. |
| `fetch_paper_text(input_str, prefer="auto"\|"html"\|"pdf")` | Full text + section split. Defaults to ar5iv HTML for arXiv papers (cheap, structured), PDF fallback otherwise. |
| `extract_methods(input_str, model=None)` | LLM-driven, Pydantic-validated structured methods extraction. Returns `{steps, reagents, equipment, analyses, confidence}`. |
| `find_code_repo(input_str)` | Discover the paper's code repo via paper text → abstract → Papers With Code. |
| `assess_repo_reproducibility(repo_url, paper_id=None)` | Heuristic, no-clone reproducibility assessment via the GitHub REST API. Weighted signals (README, deps, fixtures, notebooks, figure scripts, recent maintenance, license) → `{verdict, score, recommended_entrypoint}`. |
| `summarize_paper(input_str, mode="tldr"\|"abstract"\|"exec")` | LLM summary in three depths. |
| `methods_repro_review(input_str)` | Composite — metadata + methods + repo + repro in one call. |

All tools return Pydantic v2 models (validated, JSON-serialisable). See [`src/methods_mcp/schemas.py`](src/methods_mcp/schemas.py) for the full type surface.

## Design notes

- **`extract_methods` uses Anthropic tool-use to coerce the model into emitting an instance of the `MethodsStructured` Pydantic schema.** On validation failure we send one repair message with the validation error and try again before raising.
- **`assess_repo_reproducibility` does not clone or execute anything.** It scores the repo from publicly-readable GitHub metadata + the recursive tree listing. This is the deliberate wedge against batch tools that try to actually rerun the paper.
- **`fetch_paper_text` prefers ar5iv HTML over PDF parsing for arXiv papers.** Falls back to `pypdf` for non-arXiv inputs.
- **The default model is `claude-sonnet-4-6`.** Override via `METHODS_MCP_MODEL` env var or per-call `model=` arg.
- **`methods_repro_review` is non-atomic.** Sub-steps run independently; any that raise contribute a `null` to the corresponding output key and push a message into `_errors`. An agent calling this tool should always check `_errors` and treat missing keys as *unavailable*, not *zero*. Example: a paper with no detectable repo returns `repro_assessment: null` and an empty `_errors` list — that's a correct "no repo found," not a failure.

## Scores & verdicts explained

Tool outputs contain three numeric fields that look similar but mean very different things. They are **triage signals for an agent deciding whether a paper is worth digging into**, not calibrated claims about correctness.

| Field | Range | How it's computed | How to read it |
|---|---|---|---|
| `methods.confidence` | 0–1 | **LLM self-report.** The extractor model sets it per instructions in the system prompt: `≥0.8` only if the paper gives explicit reagents/volumes/equipment, `~0.3` if the methods section is sparse. Uncalibrated. | Soft signal for *"is this a wet-lab paper with concrete procedure, or a sparse systems paper?"* Useful as a flag; don't treat as a trust percentage. |
| `code_repo.confidence` | 0–1 | **Varies by `detection_method`.** `papers-with-code`: fixed `0.95` (authoritative paper→repo API). `paper-text`: computed as `0.6 + 0.2·(strong-phrase-present) + 0.015·score_margin`, capped at `0.95`. `abstract-link`: fixed `0.85`. `none`: `0.0`. | Tells you **how** the repo was found and how decisively. High score + `paper-text` means a strong phrase like *"code is available at …"* sat next to the URL. |
| `repro_assessment.overall_score` | 0–1 | **Weighted sum of 8 binary signals**, all computed from the GitHub REST API (no clone, no execution): `has_readme` (0.10), `readme_substantial` (0.15), `has_dependencies_file` (0.20), `has_data_or_fixtures` (0.10), `has_notebook` (0.10), `has_figure_script` (0.20), `actively_maintained` (0.10), `permissive_license` (0.05). Each present signal contributes its weight. | The only fully-deterministic score of the three. Still a heuristic, not a proof — a high score means the repo **looks** well-structured for reproduction. For actual validation see [Paper2Agent](https://arxiv.org/abs/2509.06917). |

**Verdict buckets** (`repro_assessment.verdict`) are thresholds on `overall_score`:

| Verdict | Score | Meaning |
|---|---|---|
| `likely-reproducible` | ≥ 0.70 | Most repro-friendly signals present. Worth trying to run. |
| `partial` | ≥ 0.45 | Some infrastructure, likely gaps. Expect to fill in missing pieces. |
| `unlikely` | ≥ 0.20 | Minimal signal. Possible code dump without the scaffolding to rerun it. |
| `insufficient-info` | < 0.20 *or* repo unreachable | Not enough to tell. Don't draw conclusions either way. |

**Enum values you'll see in outputs:**

- `code_repo.detection_method`: `paper-text` | `abstract-link` | `papers-with-code` | `metadata` | `none`
- `metadata.source`: `arxiv` | `biorxiv` | `doi` | `url` | `unknown`

## Security & limitations

What this server *actually* does when you install and run it:

- **Network calls only to**: `export.arxiv.org`, `ar5iv.labs.arxiv.org`, `arxiv.org` (PDFs), `api.github.com`, `paperswithcode.com`, `api.anthropic.com`. No telemetry, no analytics, no phone-home.
- **Reads** `ANTHROPIC_API_KEY` (required for LLM tools) and optionally `GITHUB_TOKEN` from environment variables. These are sent only to Anthropic / GitHub respectively. Never logged, never persisted to disk.
- **Writes** nothing to your filesystem. No cache directories, no downloaded PDFs, no temp files.
- **Executes** no user-supplied code. No `eval`, `exec`, `subprocess`, `pickle.loads`, or shell-outs. The reproducibility tool deliberately *does not* clone or run repositories — it scores from the GitHub REST API only.

**Limitations to be aware of:**

- **Adversarial papers may produce misleading structured output.** The `extract_methods` tool sends paper text to Claude. A paper containing prompt-injection content could yield wrong (but schema-valid) structured methods. Treat the output as a research aid, not ground truth.
- **The reproducibility verdict is a heuristic, not a proof.** A high score means the repo *looks* well-structured for reproduction; it does not guarantee that running the code reproduces the paper. For full validation see [Paper2Agent](https://arxiv.org/abs/2509.06917).
- **Intended for local stdio use.** The HTTP/SSE transports are provided for development convenience but should only be exposed on trusted networks (no SSRF protection beyond what httpx provides).

**Reporting issues:**

Security issues: please email flynnlachendro@hotmail.co.uk (also see [`SECURITY.md`](SECURITY.md)). Functional bugs: open a [GitHub issue](https://github.com/FlynnLachendro/methods-mcp/issues).

## Pair with `paper-mcp`

For broader paper search / citation graph tooling, run [`paper-mcp` (Bhvaik)](https://pypi.org/project/paper-mcp/) alongside in the same Claude Code session. `paper-mcp` does title-keyed search, full-text fetch, citations, and references; `methods-mcp` adds the structured-methods + reproducibility layer on top. The two were intentionally designed to compose.

## Develop locally

```bash
git clone https://github.com/FlynnLachendro/methods-mcp
cd methods-mcp
uv sync --extra dev --extra agent

uv run pytest                      # 49 tests, offline (respx-mocked httpx + unittest.mock for Anthropic)
uv run ruff format .
uv run ruff check . --fix
uv run mypy src

uv run methods-mcp --help
```

## Project notes

`project-thoughts.md` (in this repo) is a running log of what we tried, what stuck, and what we cut while building this. Honest write-up for the WWSF Loom narration.

## License

MIT — see [`LICENSE`](LICENSE).

## Acknowledgements

Built for the [Worldwide AI Science Fellowship](https://www.aisciencesummit.com/) inaugural cohort. Thanks to Michael Raspuzzi for the open-ended brief.

Built on:
- [FastMCP 3.x](https://github.com/jlowin/fastmcp) — the MCP server scaffold.
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) — the agent loop in the demo.
- [ar5iv.labs.arxiv.org](https://ar5iv.labs.arxiv.org/) — clean HTML for arXiv papers.
- [Anthropic Claude](https://platform.claude.com) — the LLM behind structured extraction.
