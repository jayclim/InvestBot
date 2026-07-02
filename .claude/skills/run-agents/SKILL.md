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
- **Fresh data every tick is REQUIRED.** Connect the Robinhood MCP (`/mcp`) before running — stock
  bars come from the MCP (step 1) and news refreshes automatically in `run_agents.py`. Don't run a
  real tick on a stale snapshot: the books won't advance and no new trades fill.

## 1. Refresh market data (REQUIRED — first, before any agent or algo, every tick)
Fetch daily bars for the whole pull list and rebuild the snapshot. Fetch `cfg.FETCH_SYMBOLS`
(the ~100-name `UNIVERSE` **plus** `cfg.BENCHMARK_SYMBOL` = SPY); `get_equity_historicals` caps at
10 symbols per call, so:
- Call `get_equity_historicals` in chunks of ≤10 symbols (`interval: day`, ~6 months). Each call overflows to a file — collect every file path.
- `python3 tools/ingest_rh.py <file1> <file2> …` (pass ALL chunk files) → rebuilds `data/snapshot.json`.
SPY rides in the snapshot like any symbol but is **never traded** (`cfg.BENCHMARKS`) — it only draws
the S&P 500 reference line on the equity chart. This MUST run before any agent/algo step every tick —
if the MCP is down, reconnect with `/mcp` and refresh before continuing; never run a real tick on stale
bars. (`run_agents.py` refreshes the news cache itself at the start of every run.)

**If the settled daily bar lags (running in the evening, before settlement):** the `day` historicals
and the official close can keep reading the *prior* session for a few hours after the 4pm ET close.
To tick on the session that just closed:
- Pull `interval: minute` for that date (13:30–20:00 UTC) for all of `cfg.FETCH_SYMBOLS`, ≤10 symbols
  per call — each call overflows to a file; collect the paths.
- Pull `get_equity_fundamentals` for the same symbols (≤10/call, ~11 chunks) — its session `volume`
  is the consolidated total. Do NOT skip this: summed minute volume undercounts by 30–70%
  (auction/off-exchange prints excluded), which silently suppresses the volume-confirmed breakout
  entries in `momentum_breakout`/`blended_momo_rsi`.
- `python3 tools/aggregate_intraday.py <date> <minute files…> --fundamentals <fundamentals files…>`
  — aggregates each name into one daily bar (volume from fundamentals; falls back to the minute sum
  with a warning) and appends/replaces it in `data/snapshot.json`.
The next normal `day` refresh overwrites the bar with the settled one.

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
One step-selectable runner now drives the whole mechanical tick. The default runs, in order:
`swarm` → `mirofish` → `analyst` → `congress` → `rules` → `dashboard`. It writes `state/swarm.json`,
`state/mirofish.json` and `state/congress.json`, reads `state/analyst.json`, rebalances each agent's
$100 paper book toward its targets, advances the rule strategies, and publishes the web state. State
accrues in `state/agent_state.json` / `paper_state.json`.

**Competitors:** `llm_voters` (independent voters, ~$0.07-0.20), `mirofish_real` (real-MiroFish
social-sim swarm — persona agents with memory interacting over rounds; **costs more**),
`deep_research_analyst` (from step 2), and `congress_mirror` (mirrors the most successful members of
Congress from a free GitHub STOCK Act feed — **free**, trades on the disclosure date; see
`tools/refresh_congress.py`).

**Always estimate cost first and tell the user** (the real-MiroFish step is the expensive one):
```
python3 run_agents.py --estimate --mirofish-tier <cheap|default|qwen>
```
Tiers: `cheap` (30×6, ~$0.10-0.25), `default` (44×10, ~$0.20-0.70), `qwen` (44×10 Qwen-plus,
~$0.70-2.00). Pass the tier when you run: `python3 run_agents.py --mirofish-tier qwen`.

**Shaping the tick (do exactly what the user asks):**
- Skip a step: `python3 run_agents.py --skip mirofish` (e.g. user says "run without the real MiroFish").
- One step only: `python3 run_agents.py --only swarm`.
- Explicit order, repeats allowed: `python3 run_agents.py --steps swarm,swarm,dashboard`.
- Steps: `swarm`, `mirofish`, `analyst`, `congress`, `rules`, `dashboard`.

When `--steps`/`--only`/`--skip` already include `rules` and `dashboard`, you do NOT also need
steps 4 and 5 below — they're folded into the runner. Run them standalone only if you skipped them.

**Order model — real-world execution (the AI agent books).** Each agent step is **settle → decide**:
first fill any orders queued on a prior run at the next available session's **open** (market-on-open,
or a limit only once the session trades through it), then plan the move toward this tick's targets and
either fill it **instantly** (if run during market hours) or **queue** it for the next open. `--fill-mode`
controls this: `auto` (default — RTH check on the ET wall clock: Mon–Fri 9:30–16:00 fills instantly,
everything else queues), or force `instant` / `queue`. Re-running supersedes an agent's still-resting
orders (that's how cancel/adjust-as-news-comes works), and equity points dedupe by date, so a
queue-only weekend run settles nothing and adds no phantom point. Queued orders show in the run summary
and publish to the dashboard (`open_orders`). The analyst can attach price-protection via an optional
`limits: {SYMBOL: price}` map in `state/analyst.json` (absent ⇒ all market-on-open). The rule
strategies already fill next-open via the engine; SPY/You are unaffected.
*Caveat:* `run_agents.py` is offline (no MCP), so an `instant` RTH fill uses the latest snapshot close,
not a live quote — refresh the snapshot first if you need a true intraday price.

**MiroFish world-events seed (optional):** if you want the real-MiroFish swarm to reason about news,
write recent headlines/signals to `state/news_seed.txt` before running; the swarm prepends it to its
briefing. Absent = it runs on price action only.

## 4. Advance the rule strategies (standalone — skip if `rules` ran in step 3)
```
python3 tick.py
```
Steps the momentum / mean-reversion / blended forward test on any new daily bar.

## 4b. Record your real portfolio (the "You" line)
Append today's real account value (and refresh the trade count) so the personal benchmark accrues
a point this tick:
1. `get_accounts` → `get_portfolio` for your **individual** real-trading account (the funded one —
   *not* the Agentic •••• cash account, which is the bots' book).
2. `get_equity_orders` for that same account; paginate all pages and **count the `filled` orders** —
   that's the cumulative trade count.
3. `python3 tools/record_me.py <session-date> <portfolio_value> <trade_count>` (same date as the tick).

**Deposits/withdrawals — keep it fair vs the always-invested algos.** If you moved external cash
in or out since the last tick (e.g. transferred $500 to your Roth), pass the NET flow so it isn't
counted as P&L: `… <trade_count> --flow -500` (deposit positive, withdrawal negative). The published
curve is **time-weighted** (`build_dashboard.twr_index`) and strips flows, so only investment return
shows. Cash interest is real return — leave it IN (don't pass it as a flow). Ask the user for the
exact transfer amount if a transfer happened; omit `--flow` when none did.

Only the rebased/normalized curve, return/max-DD, and the trade **count** are published
(`build_dashboard.me_competitor`); the real dollar value and the actual trades (symbols, dates,
sizes, prices) stay local in the gitignored `state/me.json` and are **never committed**. The "You"
row is deliberately non-clickable — no holdings or trade log. Skip this whole step if the MCP is
down — the line just holds its last point and last count until the next tick.

## 5. Publish the web app state (standalone — skip if `dashboard` ran in step 3)
```
python3 tools/build_dashboard.py   # writes web/public/state.json + history.json
```
To view locally: `cd web && npm run dev` → http://localhost:3000.
If the Vercel site is set up, publish the new state so the hosted site updates:
`git add web/public/state.json web/public/history.json && git commit -m "tick: <date>" && git push` (Vercel auto-deploys on push).
The site's live-price panel updates on its own via `/api/quotes`; only the bake-off state needs a push.

## 6. Report back
Summarize: what each agent bought/sold and why, the new standings, and any disagreement
between the analyst, the swarm, and the rule strategies.

## Guardrails & going live
- **Paper only.** Do not implement or call real-order placement in this flow.
- **Cost:** the swarm is ~$0.07-0.20/run on OpenRouter; the real-MiroFish swarm is the expensive
  one (~$0.10-2.00/run depending on tier) — **always `--estimate` and tell the user before running it**,
  or `--skip mirofish` to leave it out. The analyst runs on the Claude Code plan.
- **Graduation bar before real money:** a competitor should survive a drawdown, keep max
  drawdown tolerable, and make enough decisions to not be luck — *and* the user must fund
  account •••• — before wiring `RobinhoodBroker`. Surface this; don't go live on your own.
