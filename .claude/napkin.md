# WWSF Challenge Napkin

Living doc for the Worldwide AI Science Fellowship (WWSF) Build Challenge — Flynn's tryout for the inaugural AI for Science fellowship (cohort runs Apr 15 → Jul 15, 2026).

---

## The Ask (one-screen)

**Challenge:** Build something new in a week using the latest AI tools. Ship a real demo. Share it in public.

**Deliverables (submit by email to Michael Raspuzzi):**
1. Build-in-public post on socials (X / LinkedIn / YouTube — long or short form, Flynn's choice)
2. Public GitHub link (code + docs)
3. 2–3 min Loom walking through process and links

**What they're grading on:**
1. Real demo — does it actually work
2. Try new things — reaching into unfamiliar tools / hardware / territory
3. Process + narration — how Flynn thinks and explains it

**Deadline:** 2026-04-20, 11:59 PT (received Apr 14 ~00:44 PT, so effectively 6.5 days)
**Time budget:** ≥6 hrs recommended, average fellowship cadence is 8–10 hrs/wk

**Response owed:** reply "Challenge accepted." to lock it in.

## Example prompts they floated
- OpenClaw agent on a Digital Ocean droplet ($12) + dashboard or LabClaw literature review
- Claude Code designing a robotic protocol (Opentrons Flex sim)
- Arduino/ESP32 + sensor (temp, pH, turbidity) → MQTT/serial → live dashboard with threshold alerts
- Fork OpenSCAD/STEP file from Open Labware, parametrically modify, render, publish

(These are illustrative, not prescriptive — "figure it out" is the vibe.)

## Flynn's edge — use this
- **Dr. Flynn Lachendro, PhD in Biomedical Engineering.** This is literally "AI for Science" — lean into the science side, not just the engineering side.
- Already ships AI products fast (Arbor = research workbench; Lattice = AI research intel dashboard; Layers = pop-sci mobile; Model Collapse = prompt-engineering roguelike).
- Strongest stack: **Python + FastAPI + SQLAlchemy async + Pydantic + React/Next + TS**. Uses Anthropic / OpenAI / Gemini / OpenRouter regularly.
- Background in research pipelines (arXiv, Semantic Scholar, paper summarization, ingestion crons) → natural fit for LabClaw-style science agents.

## What "try new things" means here
To avoid this being "Flynn ships another web app," reach into at least one of:
- Real lab hardware / simulators (Opentrons Flex sim, OpenClaw, OT-2 protocol API)
- Physical-world I/O (ESP32 / Arduino / Pi, sensors, MQTT)
- Agentic lab workflows (LabClaw skills, MCP servers for scientific tooling)
- Parametric CAD / Open Labware (OpenSCAD, STEP manipulation)
- World models or VLA (video-language-action) perception

---

## Flynn Preferences (general, durable)

**Identity**
- Dr. Flynn Lachendro — PhD Biomedical Engineering, AI engineer/researcher, Founding Engineer at Nur Opus (Prism). Faculty / OpenKit background. Focus: multi-agent systems, LLM eval, AI safety.

**Collaboration style**
- **Always wait for explicit go-ahead** before git commit/push, PRs, or any irreversible action. "Should I do X?" ≠ "do X."
- No destructive-first instincts. `rm -rf`, recreating environments, `--no-verify` — only as last resort, after alternatives fail.
- No legacy wrappers / backwards-compat shims for internal refactors. Update call sites directly.
- Commit messages: short, single-line. No `Co-Authored-By`, no multi-paragraph bodies.

**Explanation style (two modes)**
- **Flynn style:** super concise, 2 ways to explain, simple analogies, minimal code, get the knack across. Used when Flynn says "explain Flynn style."
- **Claude style:** full clean written explanation in the response, then call the `say_tts` MCP (default voice) to read it aloud. Used when Flynn says "explain Claude style" or "read out Claude style."

**Package / tooling**
- `uv` for all Python. Avoid venvs.
- `ruff format .` → `ruff check . --fix` → `mypy <pkg>` → `pytest -v` is the "Linting, Typing and Checking" sequence.
- Stack defaults: FastAPI + SQLAlchemy 2.0 async + Pydantic + loguru (BE). Next.js + React + TS + Tailwind (web). Expo + RN + Reanimated (mobile). Supabase (auth + Postgres). Vercel (FE) + Railway (BE).

**Code snippets**
- When showing DB models / architectural primitives: full type annotations, both sides of relationships, `__tablename__` included. No pseudocode for real DB models.

**Root-markdown refresh**
- When Flynn says "refresh the root markdowns": review root `.md`s against current code, surgical updates (preserve style/tone), don't create new ones, report what changed.

**Granola**
- "Look through my Granola" → read `~/Library/Application Support/Granola/cache-v6.json`. `cache.state.documents` = meetings, `cache.state.transcripts` = full text keyed by doc ID.

---

## Build Log
*(fill in as we go — what was tried, what worked, what got cut, links to commits / tweets / Loom)*

- 2026-04-14 — Challenge received. Napkin set up. Planning session in progress.
- 2026-04-14 — Plan locked: build a FastMCP server primitive, demo via Claude Code live, audience = AI-for-science community (cross-domain).
- 2026-04-14 — Pivot: `paper-mcp` already exists on PyPI (Bhvaik). Paper2Agent (Stanford) does batch methods+repro. **Wedge: lightweight, on-demand, real-time MCP for methods extraction + reproducibility *heuristics*** — no full re-execution required. Package name: **`methods-mcp`**.
- 2026-04-14 (Day 1, single session) — **Day 1 fully closed.** Shipped: 8 FastMCP tools, Pydantic v2 schemas, LLM wrapper with schema-forced extraction, ar5iv HTML extractor, pypdf fallback, GitHub-API repro heuristics, console script, 29 passing tests (offline, respx-mocked), mypy strict clean, ruff clean. Built sdist + wheel locally (`dist/methods_mcp-0.1.0*`). Verified live arXiv fetch + repo discovery + repro assessment on the Paper2Agent paper — heuristic returned 0.9 likely-reproducible on AlphaGenome (matches Paper2Agent's 100% figure-regen claim). Drafted X thread + LinkedIn long-form + Loom script in `marketing/`. Verified server starts on stdio and responds to MCP `initialize` JSON-RPC.

## Open Questions / Decisions
*(TBD after the plan-mode interview)*

## Submission Checklist
- [x] Reply "Challenge accepted." to Michael Raspuzzi
- [x] GitHub repo (private → flip public before submission)
- [x] PyPI: methods-mcp 0.1.3 live
- [x] MCP Registry: io.github.FlynnLachendro/methods-mcp v0.1.2 live (0.1.3 pending re-login)
- [x] 29 tests passing + mypy strict + ruff clean + Dependabot on
- [x] Security docs: Security & Limitations README section, SECURITY.md, alpha framing
- [x] Marketing drafts ready: Loom script, X thread, LinkedIn long, single-tweet
- [ ] Build-in-public post posted (draft in `marketing/build-in-public-post.md`)
- [ ] 2–3 min Loom recorded with Kap (script in `marketing/loom-script.md`)
- [ ] Yank PyPI 0.1.0 (Flynn clicks in web UI)
- [ ] Enable PyPI 2FA
- [ ] Revoke leaked GitHub OAuth token (was in commit 4686cd4)
- [ ] Flip GitHub repo to public
- [ ] Submission email sent to Michael by **2026-04-20 23:59 PT**
