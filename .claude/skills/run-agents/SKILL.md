---
name: run-agents
description: Run one paper-trading tick of the trading bot — refresh market data, run the research analyst and the mirofish swarm on FAKE money, advance the rule strategies, and rebuild the dashboard. Use when the user says "run the agents", "run a tick", "run the bot", "/run-agents", or asks to update the paper bake-off / standings.
---

# Run a paper-trading tick

Everything here is **fake money**. Never place a real Robinhood order in this flow. The
`RobinhoodBroker` adapter is a deliberate stub; real trading only happens after the user
explicitly graduates a strategy AND funds the Agentic account ••••.

Run these steps in order. Tell the user what each agent bought/sold and why at the end.

## 0. Preconditions
- `data/snapshot.json` exists (the price history the agents read).
- For a live swarm: `OPENROUTER_API_KEY` is in `.env`. Without it the swarm falls back to a mock.
- For fresh prices: the Robinhood MCP is connected (`/mcp`). If it isn't, skip step 1 and use the existing snapshot — say so.

## 1. Refresh market data (preferred, needs Robinhood MCP)
Fetch daily bars for the whole universe and rebuild the snapshot. `cfg.UNIVERSE` is ~100 names and `get_equity_historicals` caps at 10 symbols per call, so:
- Call `get_equity_historicals` in chunks of ≤10 symbols (`interval: day`, ~6 months). Each call overflows to a file — collect every file path.
- `python3 tools/ingest_rh.py <file1> <file2> …` (pass ALL chunk files) → rebuilds `data/snapshot.json`.
If the MCP is down, skip this and note the snapshot is stale.

## 2. Produce the analyst report (agent-driven — via the financial-analyst skill)
Run the **`financial-analyst`** skill (`.claude/skills/financial-analyst/SKILL.md`). It applies the
Claude for Financial Services **equity-research** methodology (screen → sector → comps → catalysts →
thesis → portfolio) over the universe and **writes `state/analyst.json`** with target weights and a
`framework` provenance field. If the official `equity-research` / `financial-analysis` plugins are
installed, it uses their `/screen`, `/sector`, `/comps`, `/catalysts`, `/thesis` skills; otherwise it
follows the same workflow manually. Data layer: Robinhood fundamentals/historicals + web_search
(no paid-vendor MCP). It produces research only — it does not place orders.

## 3. Run the agents on fake money
```
python3 run_agents.py
```
This runs the swarm live (~150 OpenRouter calls, ~$0.20 — mention the cost), writes
`state/swarm.json`, reads `state/analyst.json`, and rebalances each agent's $100 paper
book toward its targets at the latest prices (it can buy several names and sell several).
State accrues in `state/agent_state.json`.

## 4. Advance the rule strategies
```
python3 tick.py
```
Steps the momentum / mean-reversion / blended forward test on any new daily bar.

## 5. Rebuild the dashboard + publish to the web app
```
python3 tools/build_dashboard.py   # writes dashboard.html AND web/state.json
open dashboard.html
```
If the Vercel site is set up, also publish the new state so the hosted site updates:
`git add web/public/state.json && git commit -m "tick: <date>" && git push` (Vercel auto-deploys on push).
The site's live-price panel updates on its own via `/api/quotes`; only the bake-off state needs a push.
(The web app is Next.js under `web/`; `tools/build_dashboard.py` writes `web/public/state.json`.)

## 6. Report back
Summarize: what each agent bought/sold and why, the new standings, and any disagreement
between the analyst, the swarm, and the rule strategies.

## Guardrails & going live
- **Paper only.** Do not implement or call real-order placement in this flow.
- **Cost:** the swarm costs ~$0.20 per run on OpenRouter (the analyst runs on the Claude Code plan).
- **Graduation bar before real money:** a competitor should survive a drawdown, keep max
  drawdown tolerable, and make enough decisions to not be luck — *and* the user must fund
  account •••• — before wiring `RobinhoodBroker`. Surface this; don't go live on your own.
