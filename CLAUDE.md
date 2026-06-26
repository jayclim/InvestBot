# Robinhood paper-trading bake-off

A local, **fake-money** "bake-off": several trading approaches each manage a $100 paper book over the
same market, so we can see which works **before** risking real money on Robinhood. The competitor
roster is the table below.
A **Next.js web app** (`web/`, deployable to Vercel) renders the results with full click-through
provenance, per-stock charts (price history + buy/sell markers + news), and live prices.

## Competitors
All start from $100 on the same latest session. The AI methods share `paper.rebalance` toward target
weights with per-agent stops + a circuit breaker (`cfg.AGENT_RISK`); the rule strategies use the
engine's walk-forward stops; SPY is buy-and-hold (never traded by the engine).

| Competitor | `kind` | How it works | Cost / data |
|---|---|---|---|
| `momentum_breakout` | algo | Buy a 20-day-high breakout confirmed by above-average volume; exit on a close below the 20-day SMA. Few big winners, many small losers. | free (snapshot OHLCV) |
| `mean_reversion` | algo | Buy when RSI(14) < 30 (oversold); sell when RSI(14) > 70 (overbought). Trades less, wins more often, smaller edge. | free |
| `blended_momo_rsi` | algo | Momentum breakout but skip entries already overbought (RSI ≥ 70); exit on trend break or RSI > 75. Avoids chasing extended moves. | free |
| `deep_research_analyst` | analyst | Claude-for-Financial-Services equity-research each tick (screen → sector → comps → catalysts → thesis → portfolio) → target weights + per-name rationale; reflects on the prior tick and grades alpha vs SPY. | Claude Code plan usage (web_search + RH) |
| `llm_voters` | swarm | 150 unique-profile cheap LLMs each cast an independent ballot over their own ~20-name slice; allocate across the top vote-getters (weight ∝ vote share, capped). | ~$0.20/run (OpenRouter) |
| `mirofish_real` | mirofish | Persona agents with memory interact over rounds, each ranking its ideas; rebalance toward the panel's rank-weighted (Borda) consensus — top `MIROFISH_MAX_NAMES`. | OpenRouter, costs more (tiered) |
| `congress_mirror` | congress | Ranks members of Congress by disclosed-trade excess return (free GitHub STOCK Act mirror), buys what the top filers disclosed purchasing in-universe, weighted by consensus; trades on the **disclosure date** (~weeks after their fill). | free (GitHub feed) |
| S&P 500 | benchmark | SPY all-in day one, buy-and-hold — the market baseline. Synthesized in `build_dashboard.py`; the engine never trades SPY. | free (snapshot) |
| `You` | me | The user's **real** Robinhood account (Individual), rebased to the shared origin so it's comparable. **Performance only**: a non-clickable line with NO holdings/trade_log published — only the normalized curve + return/max-DD + a trade *count*. Real $ stays in gitignored `state/me.json`. | free (RH MCP) |

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
  It screens the universe in **randomized order** (anti-bias) and writes a per-name **`rationale`** map; the site
  renders each analyst trade with its own reasoning (short = inline, long = an expandable dropdown).
  Official plugins (optional, user-installed): `claude plugin marketplace add anthropics/financial-services`
  then `claude plugin install equity-research@claude-for-financial-services`. No paid-vendor MCP connectors
  here, so the data layer stays Robinhood + web_search.
- Manual:
  - `python3 run_agents.py` — agents tick: runs the swarm live (~$0.20), pulls the congress feed (free),
    and rebalances every agent book (analyst, swarm, MiroFish, congress-mirror).
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
  - `paper.py` — the AI agents' $100 paper books + multi-name `rebalance` toward target weights
    (`swarm_targets` / `mirofish_targets` / `analyst_targets` / `congress_targets`).
  - `swarm.py` — `llm_voters` via **OpenRouter**: 150 fish across a heterogeneous model mix (`FISH_MODELS`:
    DeepSeek / Gemini / Qwen / Llama / Haiku), each a UNIQUE persona×risk×horizon×quirk
    profile. Each fish sees its OWN random ~20-name slice of the universe (`VOTER_SLICE`) with a random
    recent headline per stock, so votes don't herd. Independent-voter election. Needs `OPENROUTER_API_KEY`.
    Headlines come from a daily Finnhub cache: `refresh_news()` sweeps every name once per calendar day
    (throttled under the free 60/min) → `state/news.json` → published to `web/public/news.json`.
- `run.py` (backtest CLI), `tick.py` (rule-strategy forward tick), `run_agents.py` (agents tick).
- `tools/build_dashboard.py` — publishes `web/public/state.json` + `history.json` from `state/`. `tools/ingest_rh.py` — RH historicals → `data/snapshot.json`.
  `tools/refresh_congress.py` — pulls the `congress_mirror`'s data from a free daily GitHub mirror of STOCK Act disclosures (`kadoa-org/congress-trading-monitor`) → `state/congress.json`. `tools/analyst_memory.py` — the analyst's carry-forward brief (holdings, realized P&L, alpha vs SPY + Sharpe, prior reflection).
  `tools/record_me.py` — appends the user's real account equity + filled-trade count to the gitignored `state/me.json` (agent pulls them from the RH MCP each tick); `build_dashboard.py` rebases that into the non-clickable `You` competitor, publishing only the normalized curve + return/max-DD + trade count — never the holdings or trades.
- `web/` — a **Next.js** (App Router) app for Vercel: dashboard reading `web/public/state.json`, with
  `/api/quotes` (live prices) + `/api/news` (headlines) + `/api/intraday` (pre/after-hours candles, Yahoo)
  serverless routes (Finnhub key from `FINNHUB_API_KEY`), click-any-ticker drill-down charts (`StockModal`,
  reading `web/public/history.json`), a per-competitor holdings table, and a **Stock pool** section listing
  the universe with full company names (`web/lib/names.js`). `build_dashboard.py` publishes `state.json` +
  `history.json`; the GitHub repo is `jayclim/InvestBot`. See `web/README.md`.
- `state/` — `paper_state.json` (algos fwd), `agent_state.json` (agents fwd), `swarm.json`, `mirofish.json`, `analyst.json`, `congress.json` (daily congress-trade cache), `news.json` (daily headline cache), `live_snapshot.json` (gitignored), `me.json` (gitignored — your real equity + trade count for the `You` line).
- `data/snapshot.json` — daily OHLCV the bots read (includes SPY for the benchmark; `cfg.BENCHMARKS` keeps it untraded).

## Data & cost
- Market data is **agent-driven** via the `robinhood-trading` MCP. **Refresh before every tick** —
  `get_equity_historicals` caps at 10 symbols/call → fetch `cfg.FETCH_SYMBOLS` (universe + SPY) in **~11 chunks**
  (`interval: day`) → `python3 tools/ingest_rh.py <files…>`. SPY rides in the snapshot like any symbol but is
  never traded (benchmark only). The MCP token expires mid-session; reconnect with `/mcp`.
- **Every competitor ticks on the same, latest session** so the deep-research analyst (which reads live
  web_search + Robinhood data) is never *ahead* of the book it trades — that lookahead is the cheat to avoid.
  If the settled `day` bar lags (evening, pre-settlement), pull `interval: minute` for that date and aggregate
  to one OHLCV bar (see the run-agents skill) rather than ticking on a stale snapshot.
- The **analyst** runs on the Claude Code plan (web_search + Robinhood data). The **swarm** runs on
  **OpenRouter** (key in `.env`, gitignored), ~**$0.20/run** for 150 fish.
- The **congress_mirror** is **free**: `tools/refresh_congress.py` pulls a public GitHub JSON mirror
  (no API key, no Cloudflare), date-cached one pull/day, and falls back to its cache if the feed is down.
  It trades only on the **disclosure date** (filings lag the actual trade by up to ~45 days) — never the
  earlier transaction date, which would be the same lookahead cheat the analyst rule above bans.

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
