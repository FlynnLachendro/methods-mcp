# Build-in-public draft — pick one, post Day 7

Three drafts: a tight X thread, a LinkedIn long-form, and a single-image-style "ship post." All link to the GitHub repo + Loom + PyPI.

---

## Option A — X thread (tweet-by-tweet, 8 tweets)

**1/**
I shipped a tiny open-source primitive for the @WorldwideStudios AI for Science Fellowship tryout: `methods-mcp` 🧪🤖

A FastMCP server that turns any academic paper into structured methods + a 30-second reproducibility verdict — for any AI agent.

Early days (alpha, 0.1.x — pin the version), but it works end-to-end.

[Loom link]

**2/**
Why this and not "another vertical AI-for-science app"?

The bottleneck for the next wave of AI-for-science agents isn't models. It's *primitives*. Every fellow shouldn't have to write paper-extraction plumbing from scratch.

So: ship the plumbing. As an MCP server. So everyone gets it for free.

**3/**
Eight tools:
- get_paper_metadata (URL/ID/DOI)
- fetch_paper_text (ar5iv HTML > PDF)
- extract_methods → Pydantic-validated structured methods
- find_code_repo
- assess_repo_reproducibility (NO clone, NO execution, just heuristics)
- summarize_paper (3 modes)
- methods_repro_review (composite)

**4/**
The wedge against @PaperToAgent (Stanford, beautiful work):

Paper2Agent: 30 minutes to hours, batch, generates a custom MCP server per paper.

methods-mcp: 5 seconds, on-demand, agent-callable. Not a replacement — the lightweight companion you reach for when you don't have an hour.

**5/**
The reproducibility tool was the surprise. We score from public GitHub metadata only:
- README quality
- deps file
- fixture data
- notebooks
- figure-generating scripts (make_figures.py etc.)
- recent maintenance
- permissive license

Eight weighted signals → verdict + recommended entrypoint.

**6/**
Receipts: ran it on the Paper2Agent paper itself. It found google-deepmind/alphagenome (the case study repo) and scored it 0.9 → "likely-reproducible".

Recommended entrypoint: `python src/alphagenome/visualization/plot.py` ← real script in the repo.

Paper2Agent's deep batch run hit 100% figure regen. Our 5s heuristic agreed. 🎯

**7/**
Try it from Claude Code in two lines:

```
/mcp add methods-mcp methods-mcp
> Run methods_repro_review on https://arxiv.org/abs/2509.06917
```

Or from the Claude Agent SDK — full demo in the repo at `examples/reflexive_demo.py`.

**8/**
Github: https://github.com/FlynnLachendro/methods-mcp
PyPI: https://pypi.org/project/methods-mcp/ (alpha — `uv add 'methods-mcp==0.1.3'`)

Process notes (what broke, what I cut) live in `project-thoughts.md` so future fellows don't trip on the same things.

Massive thanks to @michaelraspuzzi + the WWSF crew. 🙏

---

## Option B — LinkedIn long-form

**Headline:** I shipped an open-source MCP server for the AI for Science Fellowship tryout. Here's the build, and what surprised me.

7 days, 1 brief: "build something using the latest AI tools." 

I'm a biomed engineer by training, AI engineer by trade. The natural play would have been "AI ghostwrites a wet-lab protocol" — which is cool, but it's a vertical demo for a niche audience. So I went a layer up: build a primitive that *every* fellow in the cohort could pick up on day 1.

**The primitive: `methods-mcp`**

A small FastMCP server that gives any AI agent (Claude Code, the Claude Agent SDK, your own thing) eight tools to:
- canonicalise a paper from any URL/ID/DOI
- extract its full text + sections
- pull out a Pydantic-validated *structured methods object* (steps, reagents, equipment, analyses) via Claude tool-use
- find the paper's code repo
- assess that repo's reproducibility — without cloning or executing anything
- summarise the paper at three depths

`uv add 'methods-mcp==0.1.3'`. That's it. Plug into Claude Code with `/mcp add methods-mcp`. Done. (It's an alpha — pin the exact version for now and expect output shapes to shift between minor releases.)

**The wedge**

There's already a beautiful paper-to-agent pipeline from Stanford called Paper2Agent. It's heavyweight: 30 minutes to hours per paper, batch processing, generates a bespoke MCP server. Different shape.

`methods-mcp` is the lightweight, real-time, agent-callable companion. The thing your agent calls in 5 seconds when it just needs structured methods or a repro signal — not a full custom server.

**The surprise**

I tested it on the Paper2Agent paper itself. The reproducibility tool found google-deepmind/alphagenome (their primary case study) and scored it 0.9 → "likely-reproducible." Recommended entrypoint: `python src/alphagenome/visualization/plot.py` — a real script in the repo.

Paper2Agent's heavyweight pipeline regenerated 100% of AlphaGenome's figures. Our 5-second heuristic agreed.

**What broke (the honest bits)**

- ar5iv now uses `<section>` tags, not `div.ltx_section` like the old docs say. And modern arXiv headings render as "1Introduction" with no separator between the number and word. My section-detection regex assumed "1." or "1)". Fixed.
- Methods sections are sometimes called "Extended Methods" or "Online Methods" — added aliases.
- mypy strict + Anthropic SDK union types is a small ceremony. `isinstance(b, ToolUseBlock)` to narrow the union.

The full process log lives in `project-thoughts.md` in the repo — written specifically so the next fellow doesn't trip on the same things.

**Where to find it**

GitHub: https://github.com/FlynnLachendro/methods-mcp
PyPI: https://pypi.org/project/methods-mcp/
2-min Loom walkthrough: [Loom link]

Huge thanks to Michael Raspuzzi and the Worldwide Studios team for the open-ended brief. The cohort kicks off this week.

#AIforScience #MCP #OpenSource

---

## Option C — Single ship post (X)

shipped `methods-mcp` for the @WorldwideStudios AI for Science Fellowship tryout.

8-tool FastMCP server. Paper URL in → structured methods + reproducibility verdict out.

The lightweight, agent-callable companion to Stanford's Paper2Agent.

Alpha — `uv add 'methods-mcp==0.1.3'` + `/mcp add methods-mcp` in Claude Code.

[Loom]
[GitHub]
