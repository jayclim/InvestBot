# InvestBot

A local, **fake-money** trading bake-off. Several approaches each manage their own virtual
**$100** over the same ~100-name market, so you get an apples-to-apples leaderboard of what
actually works — **before** risking a real dollar on Robinhood.

> **Paper money only.** `bot/broker.py: RobinhoodBroker` is an intentional stub; nothing here
> places a real order. Going live is gated — see [Going live](#going-live-later-gated).

## The competitors

Every competitor starts from **$100** and trades the same ~100-name market; the dashboard ranks them
with full click-through provenance, and the equity chart overlays the **S&P 500** as a benchmark.

| Competitor | Type | How it works | Cost |
|---|---|---|---|
| `momentum_breakout` | rule strategy | Buys a 20-day-high breakout confirmed by above-average volume; exits on a close below the 20-day SMA. A few big winners, many small losers. | free |
| `mean_reversion` | rule strategy | Buys oversold (RSI(14) < 30), sells overbought (RSI > 70). Trades less, wins more often, smaller edge. | free |
| `blended_momo_rsi` | rule strategy | Momentum breakout, but skips entries already overbought (RSI ≥ 70) and exits on a trend break or RSI > 75 — avoids chasing extended moves. | free |
| **Research analyst** | deep research | Runs Anthropic's *Claude for Financial Services* equity-research methodology each tick (screen → sector → comps → catalysts → thesis → portfolio) → target weights with a per-name rationale; grades its prior tick against the S&P 500 and adjusts. | Claude Code plan |
| `llm_voters` | LLM swarm | 150 cheap LLMs (via OpenRouter), each a unique `persona × risk × horizon × quirk` profile voting on its own random ~20-name slice — an independent-voter election whose slices keep votes from herding. | ~$0.20/run |
| `mirofish_real` | social swarm | Persona agents *with memory* that interact over rounds (a social simulation — the opposite of the independent vote); the book follows their rank-weighted consensus. | OpenRouter (more) |
| `congress_mirror` | politician mirror | Ranks members of Congress by the excess return of their disclosed trades (a free GitHub mirror of public STOCK Act filings), then buys what the top performers disclosed purchasing — on the **disclosure date**, which by law lags their actual trade by up to ~45 days. | free |
| **S&P 500** | benchmark | SPY bought all-in on day one and held — the market baseline. Drawn on the chart but never traded by the engine. | free |
| **You** | real account | The user's **real** Robinhood portfolio, rebased to the shared origin so it's comparable. Deposits/withdrawals are stripped via a time-weighted return, so transfers in/out aren't read as P&L. **Performance only** — a non-clickable line publishing the normalized curve + return/max-DD + a trade *count*, never the holdings or trades. Real $ stays in a gitignored file. | free |

## Run it

This project is **agent-driven** — a Claude Code agent fetches market data (the `robinhood-trading`
MCP), runs the analyst + swarm, and advances the books. The easy button:

> say **“run the agents”** — the `run-agents` skill: refresh data → analyst report → swarm → advance books → publish web state.

Manual pieces (stdlib-only Python, except `httpx` for the swarm):

```bash
python3 run.py                    # backtest only — prints the leaderboard
python3 tick.py                   # advance the rule strategies one session
python3 run_agents.py             # run the swarm + rebalance the AI agents' books (needs OPENROUTER_API_KEY)
python3 tools/build_dashboard.py  # publish web/public/state.json + history.json (no API calls)
```

## The dashboard

The **`web/`** app is the dashboard — a **Next.js** app (deployable to Vercel) that fetches the
bake-off state (`web/public/state.json`), **live-polls real prices** (`/api/quotes`, Finnhub), pulls
**headlines** (`/api/news`), and lets you **click any ticker** for its price chart with each method's
buy/sell markers. The **equity curves** overlay the S&P 500 as a dashed benchmark; the **decision
trail** is colour-coded by method with per-method filtering. Orders placed outside market hours
**queue** and fill at the next open — those resting orders show in the decision trail and each
competitor's popup until they fill. Each competitor has a holdings table, and a **Stock pool**
section lists the universe with full company names. See
[`web/README.md`](web/README.md). (`build_dashboard.py` also publishes `web/public/history.json`
for those charts and `web/public/news.json`, the daily headline cache.)

Standings, curves, and the decision trail are the **live forward books** (every competitor from
$100, same method). Dollar/share figures are shown scaled to a **$10,000 notional** for readability —
the real books are $100; scaling is applied once in `build_dashboard.py` (per-share prices and % stay
real). A Dec–Jun walk-forward backtest is kept as per-strategy reference, not the board.

## Risk controls (the “not gambling” part)

- Hard stop per position (`STOP_LOSS_PCT`, default 15%)
- Max open positions (`MAX_POSITIONS`, default 5) + a per-name cap for the agents (`AGENT_MAX_WEIGHT`)
- Equity circuit breaker (`CIRCUIT_BREAKER_EQUITY`, default $60) halts new buys
- Simulated slippage on every fill so paper results aren't flattering

## Going live (later, gated)

Only after a competitor clears a graduation bar (survived a drawdown, enough decisions, tolerable
max DD) **and** the Agentic cash account (`••••`) is funded do we wire `RobinhoodBroker`. That
account is cash, **no options**, so this harness is equities/ETFs only. The account number is read
from `AGENTIC_ACCOUNT` in a gitignored `.env` — never stored in source.

## Configuration & secrets

- Knobs live in `bot/config.py` (universe, risk limits, signal params).
- Secrets go in a **gitignored `.env`**: `OPENROUTER_API_KEY` (swarm) and `AGENTIC_ACCOUNT` (go-live).
  The web app reads `FINNHUB_API_KEY` from `web/.env.local` (local) or a Vercel env var (deployed).

## More

Architecture, conventions, and the agent workflow are in **[`CLAUDE.md`](CLAUDE.md)**.
