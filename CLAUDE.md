# Robinhood paper-trading bake-off

A local, **fake-money** "bake-off": several trading approaches each manage a $100 paper book over the
same market, so we can see which works **before** risking real money on Robinhood. Competitors are 3
rule strategies + a deep-research **analyst** + `llm_voters` (150 cheap-LLM independent voters) + a
real-MiroFish social-sim swarm. The equity chart also overlays the **S&P 500** (SPY) as a benchmark.
A **Next.js web app** (`web/`, deployable to Vercel) renders the results with full click-through
provenance, per-stock charts (price history + buy/sell markers + news), and live prices.

## Golden rules
- **Paper money only. Never place a real Robinhood order.** `bot/broker.py: RobinhoodBroker` is an
  intentional stub. `run_agents.py` / `tick.py` / `build_dashboard.py` only touch paper state.
- **Going live requires ALL of:** a competitor clears a graduation bar (survived a drawdown, tolerable
  max DD, enough decisions to not be luck) **+** the user funds the Agentic account (••••) **+**
  explicit user go-ahead to wire `RobinhoodBroker`. Never do this unprompted.
- The **Agentic cash account ••••** is the only account that accepts agent orders — cash, no
  options, currently **unfunded ($0)**. Its number is read from `AGENTIC_ACCOUNT` in the gitignored
  `.env` (`config.AGENTIC_ACCOUNT` defaults to empty) — never hard-code it in source.

## Run it
- Say **"run the agents"** / `/run-agents` → follows `.claude/skills/run-agents/SKILL.md`
  (refresh data → write analyst report → `run_agents.py` → `tick.py` → rebuild dashboard).
- The analyst step uses the **`financial-analyst`** skill — Anthropic's Claude for Financial Services
  *equity-research* methodology (screen → sector → comps → catalysts → thesis → portfolio) → `state/analyst.json`.
  Official plugins (optional, user-installed): `claude plugin marketplace add anthropics/financial-services`
  then `claude plugin install equity-research@claude-for-financial-services`. No paid-vendor MCP connectors
  here, so the data layer stays Robinhood + web_search.
- Manual:
  - `python3 run_agents.py` — agents tick: runs the swarm live (~$0.20) + rebalances both agent books.
  - `python3 tick.py` — advance the rule strategies' forward test by one session.
  - `python3 tools/build_dashboard.py` — publish `web/public/state.json`, `history.json` **and** `news.json` from `state/` (no API calls).
  - `python3 run.py` — backtest only (prints the leaderboard).

## Layout
- `bot/` — stdlib-only package:
  - `config.py` — ~100-name `UNIVERSE`, risk knobs (`SLIPPAGE_BPS`, `STOP_LOSS_PCT`, …), `AGENT_*`, `AGENTIC_ACCOUNT`,
    plus `BENCHMARK_SYMBOL`/`BENCHMARKS` (SPY — charted but never traded) and `FETCH_SYMBOLS` (= `UNIVERSE` + SPY, the data-refresh pull list).
  - `models.py`, `indicators.py`, `portfolio.py`, `broker.py` — primitives (`PaperBroker`, stub `RobinhoodBroker`).
  - `strategy.py` — 3 rule strategies: `momentum_breakout`, `mean_reversion`, `blended_momo_rsi`.
  - `engine.py` — walk-forward replay + `step_day` (decide on prior close, fill next open, slippage/stops).
  - `metrics.py` — performance summary. `state.py` — algo forward-test persistence.
  - `paper.py` — the AI agents' $100 paper books + multi-name `rebalance` toward target weights.
  - `swarm.py` — `llm_voters` via **OpenRouter**: 150 fish, each a UNIQUE persona×risk×horizon×quirk
    profile. Each fish sees its OWN random ~20-name slice of the universe (`VOTER_SLICE`) with a random
    recent headline per stock, so votes don't herd. Independent-voter election. Needs `OPENROUTER_API_KEY`.
    Headlines come from a daily Finnhub cache: `refresh_news()` sweeps every name once per calendar day
    (throttled under the free 60/min) → `state/news.json` → published to `web/public/news.json`.
- `run.py` (backtest CLI), `tick.py` (rule-strategy forward tick), `run_agents.py` (agents tick).
- `tools/build_dashboard.py` — publishes `web/public/state.json` + `history.json` from `state/`. `tools/ingest_rh.py` — RH historicals → `data/snapshot.json`.
- `web/` — a **Next.js** (App Router) app for Vercel: dashboard reading `web/public/state.json`, with
  `/api/quotes` (live prices) + `/api/news` (headlines) + `/api/intraday` (pre/after-hours candles, Yahoo)
  serverless routes (Finnhub key from `FINNHUB_API_KEY`), click-any-ticker drill-down charts (`StockModal`,
  reading `web/public/history.json`), a per-competitor holdings table, and a **Stock pool** section listing
  the universe with full company names (`web/lib/names.js`). `build_dashboard.py` publishes `state.json` +
  `history.json`; the GitHub repo is `jayclim/InvestBot`. See `web/README.md`.
- `state/` — `paper_state.json` (algos fwd), `agent_state.json` (agents fwd), `swarm.json`, `mirofish.json`, `analyst.json`, `news.json` (daily headline cache), `live_snapshot.json` (gitignored).
- `data/snapshot.json` — daily OHLCV the bots read (includes SPY for the benchmark; `cfg.BENCHMARKS` keeps it untraded).

## Data & cost
- Market data is **agent-driven** via the `robinhood-trading` MCP. `get_equity_historicals` caps at
  10 symbols/call → fetch `cfg.FETCH_SYMBOLS` (universe + SPY) in **~11 chunks** → `python3 tools/ingest_rh.py <files…>`.
  SPY rides in the snapshot like any symbol but is never traded (benchmark only). The MCP token expires mid-session; reconnect with `/mcp`.
- The **analyst** runs on the Claude Code plan (web_search + Robinhood data). The **swarm** runs on
  **OpenRouter** (key in `.env`, gitignored), ~**$0.20/run** for 150 fish.

## Conventions
- **Never add Claude / yourself as a contributor or co-author.** Commit as jayclim with **no**
  `Co-Authored-By` trailer, and don't credit AI anywhere — commits, PRs, README, `package.json`, or this file.
- Stdlib-only except `httpx` (swarm) — see `requirements.txt`.
- The dashboard is the `web/` app reading `web/public/state.json`; every figure traces to a source (see
  its "Methods & sources" section and the ⓘ explainers).
- **Display scale:** the real paper books are $100 (in `state/`), but the web shows every dollar/share
  figure scaled to a **$10,000 notional** for readability. The scale is applied once in
  `build_dashboard.py` (`DISPLAY_SCALE`); per-share prices and percentages stay unscaled. Change that one
  constant to re-scale the whole site.
- **Standings / curves / decision trail = the LIVE forward books** (all competitors from $100, same
  method). The Dec–Jun walk-forward backtest is **reference only**, shown inside each rule strategy's
  row detail — not the live board.

## More context
Design rationale, decisions, and history are in the project auto-memory:
`~/.claude/projects/-Users-jaydenl-Dev-Stocks-robinhood/memory/trading-bot-project.md`.
