# Changelog

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
