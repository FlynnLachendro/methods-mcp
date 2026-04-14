# project-thoughts.md

A running log for the WWSF Build Challenge — what I tried, what stuck, what I cut. Written so I can grab quotes for the 2-min Loom narration on Day 7.

---

## 2026-04-14 — Mon, Day 1

### Why I'm building this thing in particular

The challenge is open-ended: "build something using the latest AI tools, in a week." My biomed PhD pulls me toward wet-lab automation, but I deliberately zoomed out — I think what's actually missing in the AI-for-science world right now isn't another vertical app, it's **better primitives for the next wave of AI-for-science builders**. So the audience for this build is the WWSF cohort itself: fellows on day 1 who want to build *their* agent without writing the same paper-extraction plumbing for the fourth time.

### How I narrowed in (and pivoted)

First instinct: paper → Opentrons protocol agent. Self-repair loop, "watch the AI write a real wet-lab experiment." Cool, but my stronger instinct was that an MCP primitive would have a longer half-life than a vertical demo. So I switched directions to:

> Build a paper-extraction MCP server. Demo it via Claude Code. Other fellows can install and use it on day 1.

Then I checked PyPI — **`paper-mcp` already exists** (Bhvaik, v0.6.0, Feb 2026). Real working project. It covers title-keyed search, S2 + arXiv + Unpaywall full text, citations, references. Roughly the entire "A core" I'd planned.

That could have killed the project; instead it sharpened it. I dug for what *isn't* covered yet:

- **Paper2Agent** (Stanford, Sept 2025, [arXiv:2509.06917](https://arxiv.org/abs/2509.06917)): does methods extraction + reproducibility checking. But it's a 30-min-to-hours batch pipeline that turns a paper into a custom MCP server — heavyweight and offline.
- Nobody has shipped the **lightweight, agent-callable, real-time MCP** for "give me this paper's structured methods + tell me how reproducible its repo looks."

That gap is the wedge. So `methods-mcp` is now framed as the on-demand companion to both `paper-mcp` (for the broader paper toolkit) and Paper2Agent (for the deep batch analysis).

### Naming

`paper-mcp` — taken. Spent ~10 minutes brute-forcing PyPI for a name that was simultaneously available, descriptive, short, and pleasant to say. Shortlist: `methods-mcp`, `vera-mcp` (Latin "truth"), `repro-mcp`. Picked `methods-mcp` for discoverability — when a fellow is grepping their MCP registry for "extract methods" they should land on us in zero clicks.

### Architectural choices, and why

- **FastMCP 3.x** — decorator-based, gives me the @mcp.tool surface in one line. Looked at the lower-level MCP SDK; FastMCP is dramatically less ceremony.
- **Pydantic v2 schemas as the source of truth** — every tool returns a typed model. The LLM extractor reuses these schemas as Anthropic tool-use input_schemas, so the LLM is *forced* to emit a payload that matches. One repair attempt on validation failure, then raise.
- **ar5iv HTML over PDF parsing for arXiv papers** — Nougat / marker / GROBID are heavyweight. ar5iv is already-rendered structured HTML, basically free. PDF fallback (pypdf) for non-arXiv. Dropped Nougat from scope on Day 1 — would have cost half my time budget.
- **No code execution for repro assessment** — this is the *real* differentiation from Paper2Agent. We score reproducibility from public GitHub metadata + recursive tree listing only. Eight weighted signals: README quality, deps file, fixture data, notebooks, figure-generating script (e.g. `make_figures.py`), recent maintenance, permissive license. Bounded, deterministic, fast.
- **Composite tool `methods_repro_review`** — collapses the four-call agent flow (metadata → text → methods → repo → repro) into one tool call so an agent can get the whole picture cheaply. The granular tools are still exposed for finer control.

### What broke / what I cut

- **`get_tools()` doesn't exist on FastMCP 3.x** — it's `list_tools()`. Found out from a failing smoke test. (Earlier `get_tool` only takes a single name.)
- **mypy strict mode + Anthropic SDK union types** — content blocks are typed as a 12-member union, only `ToolUseBlock` carries `.id`. Switched the lookup from `getattr(b, "type", ...) == "tool_use"` to `isinstance(b, ToolUseBlock)`, which narrows the union for mypy.
- **noqa: BLE001 noise** — initial draft sprinkled `# noqa: BLE001` on broad except clauses out of habit. Our ruff config doesn't enable BLE, so ruff flagged the noqa as unused. Removed them.
- **Dropped from scope (deliberately)**: PDF reproducibility execution (Docker sandbox + figure comparison), broader source coverage (ChemRxiv, NASA ADS), MCP Resource exposure beyond Tools. All of these are good candidates for v0.2.

### Where I am now

Day 1 evening: **scaffold, all 8 tools, Pydantic schemas, llm wrapper, 29/29 tests passing, mypy strict clean, ruff clean, console script working.** Faster than budgeted because the scope shrank with the pivot. Tomorrow: live arxiv smoke run + Agent SDK demo + asciinema GIF + PyPI publish.

### Live smoke test (Day 1, late) — caught a real parser bug

I pointed the local server at the actual Paper2Agent paper (arxiv 2509.06917) to check the end-to-end path. arXiv metadata: clean. ar5iv full text: 41k chars extracted. **Sections detected: only `abstract`** — methods, results, intro, all empty.

Investigation: ar5iv now uses `<section>` tags (not `div.ltx_section`), and headings on this paper render as `1Introduction` (no separator between number and word) rather than `1. Introduction`. My `_norm_heading` regex required a `.` or `)` after the leading number, so `"1introduction"` failed every alias check and the section was silently skipped. Also: the paper's methods section is titled `Extended Methods`, which wasn't in `SECTION_ALIASES`.

Fix:
- Loosened the leading-numbering regex to optional separator (`[\.\)\-:]?`).
- Added aliases: `extended methods`, `online methods`, `supplementary methods` → `methods`.

After the fix: `['introduction', 'results', 'discussion', 'methods', 'abstract']` — 13.6k chars in the methods section, beginning "Details on implementing Paper2Agent. Paper2Agent converts a research paper and its public codebase into a production-ready MCP server..."

Lesson: the "lightweight wedge" of using ar5iv HTML over PDF parsing is the right call, but the heuristics need to be tested against real, non-trivial papers — not just synthetic fixtures. Adding more real-world papers to the fixtures list is on the v0.2 roadmap.

### The "we agree with Paper2Agent" result

`methods_repro_review` against the Paper2Agent paper auto-discovered the [google-deepmind/alphagenome](https://github.com/google-deepmind/alphagenome) repo (because the paper text mentions it as their primary case study) and scored it **0.9 / 1.00 → "likely-reproducible"**. Recommended entrypoint: `python src/alphagenome/visualization/plot.py`, which is a real script in the repo.

The Paper2Agent paper claims they got 100% figure-regeneration accuracy on AlphaGenome via their heavyweight batch pipeline. Our 30-second heuristic landed at the same conclusion — likely reproducible. That's not proof the heuristic is right in general, but it's a nice "our cheap signal correlates with their expensive ground truth" data point. I'll mention this in the Loom.

### Live LLM call, dev-env caveat

Tried to live-test `extract_methods` against the same paper. Got `anthropic.AuthenticationError: 401 invalid x-api-key`. The dev shell has a key set by Claude Code's own runtime that isn't valid for direct API calls. End users will need to export their own `ANTHROPIC_API_KEY`. The code path runs through to the API correctly — auth is the only blocker, which README already calls out.

