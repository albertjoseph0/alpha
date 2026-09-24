# Running the research agents locally (on your own Claude credits)

1. On your computer:
   ```bash
   git clone <this repo's URL> alpha && cd alpha
   git checkout claude/gracious-brown-m9t9wj && git pull
   uv venv .venv && uv pip install --python .venv/bin/python pandas numpy pyarrow yfinance scipy scikit-learn lightgbm torch pymupdf
   ```
2. **Jev access.** The cloud session reached Jev through the Vercel AI Gateway, with the key injected by the cloud proxy.
   Locally, set `AI_GATEWAY_API_KEY` in your shell. `research/round5/jev.py` sends it as a Bearer token when the
   variable is set.
3. Start Claude Code in the folder (`claude`, or `claude remote-control` to also see it in the Claude Code app) and
   paste this prompt:

---
You are the orchestrator of a trading-strategy research project in this repository. Read `HANDOFF.md`,
`research/round5/BRIEF.md`, `research/round6/BRIEF_JEV.md` and `research/round5/RESULTS_TRACKER.md` first.
Then:
1. For every agent listed in HANDOFF.md whose folder has no README.md, spawn a background subagent
   (general-purpose, same model as you) with this prompt: "You are research agent <id> in <repo path>,
   resuming after the previous session ended. Read research/round5/BRIEF.md (and research/round6/BRIEF_JEV.md
   for j0x and o0x), then your folder's STATUS.md, and continue from its next step. Keep STATUS.md up to date;
   finish with README.md." Also resume the orchestrator's own projects o01 (research/orch/o01_activist_13d) and
   o02 (research/orch/o02_beige_book) the same way; their STATUS is in HANDOFF.md.
2. When an agent finishes, review its README critically: check for lookahead, survivorship and overfitting.
   Add a row to RESULTS_TRACKER.md, then commit and push.
3. Keep 8–12 agents running. When slots free up, launch new Jev-focused ideas from
   `research/round6/CANDIDATES.md`, or new ones built on what the finished agents learned. Every new agent
   gets the same briefs, a PREREG.md and a sealed TEST period.
4. Continue until I say stop or the credits run out. Commit and push after every milestone.
---
