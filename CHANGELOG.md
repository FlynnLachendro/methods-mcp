# Changelog

## 0.1.7 — 2026-04-15

**Fix: `.rstrip(".git")` bug was only half-fixed in 0.1.5.** The same footgun existed in `quick_repo_assessment` (line 277) as well as `find_repo_in_text`. 0.1.5 patched only the latter. As a result, `assess_repo_reproducibility("https://github.com/jmiao24/Paper2Agent")` was querying `api.github.com/repos/jmiao24/Paper2Agen` (trailing `t` stripped from the repo name), getting 404, and returning `verdict: insufficient-info` with the misleading note *"Repo not found or GitHub API unreachable."* Replaced with `str.removesuffix(".git")`. New regression test mocks the correct (unstripped) URL path, so if the bug returns the test fails to match and surfaces.

Discovered by live-testing via MCP Inspector against the Paper2Agent repo, same methodology that surfaced the 0.1.5 fix. Tests 73 → 74.

## 0.1.6 — 2026-04-15

**`methods_repro_review` output is now self-describing in plain English — minimal tool-learning required.**

- **New top-level `status` field** (`"ok"` / `"partial"` / `"empty"`). One-look signal for whether the call fully succeeded, partially succeeded, or couldn't even resolve the input paper.
- **New top-level `narrative` field** — plain-English summary of everything retrieved, with every numeric score echoed in context ("moderate confidence (0.72)", "verdict: likely reproducible", "Present signals: README, …"). A reader can understand the whole result from `narrative` + `status` alone, without reading the README.
- **Structured `errors` replaces `_errors`.** Each entry is now `{step, error_type, message, hint?}` with an actionable plain-English `hint` for recognised failure patterns (missing `ANTHROPIC_API_KEY`, rate-limits, 404s, timeouts, invalid-LLM-response, encrypted-PDF). Unrecognised patterns leave `hint` as `null` rather than fabricating advice.
- **New `MethodsReproReview` Pydantic return type.** The composite tool now returns a validated model instead of a raw dict. Sub-objects are `null` when the corresponding step failed or was not applicable (e.g. `repro_assessment: null` when no repo was detected).
- **Narrative-building logic lives in `methods_mcp.narrative`** — a pure module with no I/O, 13 unit tests.
- **Breaking** (0.1.x alpha, so fair game): `_errors: list[str]` is gone. Callers that depended on it should switch to `errors: list[{step, error_type, message, hint}]`.
- **Two bugs caught by live-testing the new output on the Paper2Agent paper** (and fixed before ship): (1) the hint classifier's schema-validation branch matched "invalid x-api-key" auth errors because of the bare `"invalid"` substring check — added a specific auth-error branch and narrowed the schema-invalid match to `error_type=="ValidationError"`; (2) when the GitHub REST API is unreachable (e.g. unauthenticated rate limit), the assessor returns a `ReproAssessment` with empty signals — the narrative now detects this and says "reproducibility assessment was unavailable" with a `GITHUB_TOKEN` hint, instead of the misleading "Present signals: none. Missing: none."
- Tests 57 → 73.

## 0.1.5 — 2026-04-15

**Two fixes to `find_code_repo` surfaced when live-testing on the Paper2Agent paper.**

- **Fix: `.rstrip(".git")` was chewing trailing characters off repo names.** `str.rstrip` takes a *set of chars* to strip, so any repo name ending in `.`, `g`, `i`, or `t` lost those characters (e.g. `jmiao24/Paper2Agent` → `jmiao24/Paper2Agen`). Replaced with `str.removesuffix(".git")`. Regression tests added.
- **Fix: repo discovery scored by surrounding phrases, not by first-match wins.** The old implementation picked the first GitHub URL in the paper text, which on papers that cite multiple repos (a paper's validation cases plus its own code) would pick a case-study repo over the paper's own. New `find_repos_in_text()` collects every URL, scores each by the phrase immediately preceding it (`STRONG_PHRASES` = "code availability" / "publicly available at" / "our code" / etc.; `MEDIUM_PHRASES` = "code:" / "available at" / etc.), and returns them sorted best-first. Dedupes across mentions with a small repeat-mention bonus. Preceding-text only (not surrounding) — prevents section-header bleed backwards.
- **Papers With Code is now tried first** for arXiv papers (authoritative paper→repo mapping) before text-scanning. Confidence bumped to 0.95 when PWC resolves.
- 8 new tests (49 → 57) covering the regression, the scoring ranking, multi-URL rankings, dedup with mention count, medium-phrase precedence, and PWC-first ordering.

## 0.1.4 — 2026-04-15

Freshness + coverage pass. No API changes.

- **Coverage**: test count 29 → 49. Added `test_llm.py` (schema-forced Anthropic tool-use, repair path, "no tool_use block" error), `test_methods_tool.py` (text-selection heuristic + authoritative field overwrites), `test_summarize_tool.py` (mode handling + fallback to raw text), `test_server_tools.py` (composite `methods_repro_review` happy path + error collection).
- **Linting**: tightened ruff config — now enforces `N` (naming), `S` (security), `A` (builtin shadowing), `PT` (pytest style), `PTH` (pathlib over os.path), `ASYNC`, `PIE`, `T20` (no stray prints in src). Replaced `os.path.*` calls with `pathlib.Path` / `PurePosixPath` where appropriate.
- **CI**: `UV_PYTHON` env set at job level so matrix Python versions (3.11/3.12/3.13) are honoured by every `uv run` step (previous runs silently re-resolved to 3.11 and skipped dev deps). Action versions bumped: `actions/checkout@v6`, `astral-sh/setup-uv@v7`.

## 0.1.3 — 2026-04-15

**Fix**: MCP `serverInfo.version` in the JSON-RPC `initialize` response was defaulting to FastMCP's version (3.2.4) instead of our package version. Clients that display server versions (Claude Code, Claude Desktop, etc.) now see the real `methods-mcp` version.

## 0.1.2 — 2026-04-14

Documentation + responsible-shipping pass. No code changes vs 0.1.1.

- Added explicit alpha-status banner to README (pin exact versions in production).
- Added "Security & limitations" section to README documenting network egress, secret handling, filesystem behaviour, and known limitations (prompt injection in paper text, repro-as-heuristic, intended local-stdio use).
- Added `SECURITY.md` with private-disclosure channel.
- Added Dependabot config (`.github/dependabot.yml`) for weekly dep updates + monthly Actions updates.

## 0.1.1 — 2026-04-14

Republish: includes the `mcp-name` ownership marker in the bundled README so the package can be claimed via the MCP Registry's verification handshake. No code changes vs 0.1.0.

## 0.1.0 — 2026-04-14

Initial release. Built for the Worldwide AI Science Fellowship build challenge.

### Tools shipped

- `health` — server liveness / config check
- `get_paper_metadata` — URL/ID/DOI → canonical metadata
- `fetch_paper_text` — ar5iv HTML primary, pypdf fallback
- `extract_methods` — LLM + Pydantic structured methods
- `find_code_repo` — paper-text → abstract → Papers With Code
- `assess_repo_reproducibility` — heuristic, no-clone, GitHub REST API
- `summarize_paper` — three modes (abstract / tldr / exec)
- `methods_repro_review` — composite tool

### Notes

- Default model: `claude-sonnet-4-6` (override with `METHODS_MCP_MODEL` env var).
- All tool returns are Pydantic v2 models.
- 29 offline tests via respx mocks, mypy strict, ruff lint clean.
