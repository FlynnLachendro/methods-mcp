# Loom script — 2:30 target

Open with Claude Code already running. Have terminal + repo + a browser tab on the GitHub repo open.

---

**0:00 – 0:15  // intro + what + who**

> "Hey, I'm Flynn — biomed-engineer-turned-AI-engineer. For my Worldwide AI Science Fellowship tryout I shipped a small open-source MCP server called `methods-mcp`. It turns any academic paper into structured methods data and a quick reproducibility verdict for any AI agent."

(B-roll: GitHub repo page, then PyPI page)

**0:15 – 0:35  // why this shape**

> "I picked this because the bottleneck for the next wave of AI-for-science isn't more models — it's better primitives. So instead of another vertical app, I built the plumbing: install with `uv add methods-mcp`, plug it into Claude Code in one line, and you can build agents on top."

(B-roll: terminal showing `uv add methods-mcp`)

**0:35 – 1:30  // the live demo**

Switch to Claude Code panel.

> "Here it is wired into Claude Code. I added the server with `/mcp add methods-mcp methods-mcp`. Now I'm asking it to analyse the Paper2Agent paper from Stanford — that's a recent agentic-AI-for-science paper."

Type into Claude Code:
> Take https://arxiv.org/abs/2509.06917 and run methods_repro_review. Summarise what the paper does, the methods steps, and how reproducible the repo looks.

(Wait for tool calls to fire, narrate as they happen)

> "Watch — get_paper_metadata fires, then methods_repro_review pulls full text from ar5iv HTML, extracts a structured methods object via Claude with a Pydantic schema, finds the GitHub repo google-deepmind/alphagenome, and scores its reproducibility from public metadata only — no cloning, no execution."

When the answer comes back:
> "Verdict: likely-reproducible, score 0.9. Recommended entrypoint: `python src/alphagenome/visualization/plot.py`. Paper2Agent's full batch pipeline got 100% figure regeneration on this same repo. Our 5-second heuristic agreed."

**1:30 – 2:00  // the wedge**

> "That's the wedge. Paper2Agent is a beautiful 30-minute-to-hours batch system that generates a custom MCP server per paper. methods-mcp is the lightweight, on-demand companion — the thing your agent calls in 5 seconds when it just needs the structured methods or the reproducibility signal."

**2:00 – 2:25  // process / what broke**

Open `project-thoughts.md`.

> "I kept a running build log in the repo. Two things broke worth mentioning: ar5iv switched from div tags to section tags and now emits headings like '1Introduction' with no separator — my regex required a period after the number, so every section was silently skipped. And methods sections are sometimes called 'Extended Methods' or 'Online Methods' which I had to alias. Honest write-up of the dead ends is in `project-thoughts.md` — designed so the next fellow doesn't trip on the same things."

**2:25 – 2:30  // outro**

> "GitHub link in the description, install with `uv add methods-mcp`, thanks Michael and the WWSF crew."

(Cut)

---

## Recording tips

- **Resolution**: 1280x720 minimum. If on retina mac, set system to scaled-larger so text is readable on phones.
- **Pre-warm**: run the Claude Code demo once before recording so the first tool call doesn't lag from a cold start.
- **Do TWO takes**: one full run, one with you re-explaining 1:30–2:00 (the wedge bit) more punchy if needed.
- **Loom auto-trim** the dead air at the start/end.
- **Closed captions on**: Loom auto-captions are good enough now.
- **Cap at 2:45** even if it feels short. Better tight than baggy.
