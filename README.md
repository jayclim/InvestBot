# InvestBot

A local, **fake-money** trading bake-off. Several approaches each manage their own virtual
**$100** over the same ~100-name market, so you get an apples-to-apples leaderboard of what
actually works — **before** risking a real dollar on Robinhood.

> **Paper money only.** `bot/broker.py: RobinhoodBroker` is an intentional stub; nothing here
> places a real order. Going live is gated — see [Going live](#going-live-later-gated).

## The competitors

- **3 rule strategies** (`bot/strategy.py`): `momentum_breakout`, `mean_reversion`, `blended_momo_rsi`.
- **A research analyst** — runs Anthropic's *Claude for Financial Services* equity-research
  methodology (screen → comps → catalysts → thesis → portfolio) and rebalances a $100 book toward
  target weights.
- **A "mirofish" swarm** — 150 cheap LLM voters (via OpenRouter), each a unique
  `persona × risk × horizon × quirk` profile, holding an independent-voter election over the watchlist.

Each trades the same market on its own; the dashboard ranks them with full click-through provenance.

## Run it

This project is **agent-driven** — a Claude Code agent fetches market data (the `robinhood-trading`
MCP), runs the analyst + swarm, and advances the books. The easy button:

> say **“run the agents”** — the `run-agents` skill: refresh data → analyst report → swarm → advance books → rebuild dashboard.

Manual pieces (stdlib-only Python, except `httpx` for the swarm):

```bash
python3 run.py                    # backtest only — prints the leaderboard
python3 tick.py                   # advance the rule strategies one session
python3 run_agents.py             # run the swarm + rebalance the AI agents' books (needs OPENROUTER_API_KEY)
python3 tools/build_dashboard.py  # regenerate dashboard.html + web/public/state.json (no API calls)
```

## The dashboard

Two front-ends, same data:

- **`dashboard.html`** — a single generated file; open it directly.
- **`web/`** — a **Next.js** app (deployable to Vercel) that fetches the bake-off state and
  **live-polls real prices** (`/api/quotes`, Finnhub). See [`web/README.md`](web/README.md).

Standings, curves, and the decision trail are the **live forward books** (every competitor from
$100, same method). A Dec–Jun walk-forward backtest is kept as per-strategy reference, not the board.

## Risk controls (the “not gambling” part)

- Hard stop per position (`STOP_LOSS_PCT`, default 15%)
- Max open positions (`MAX_POSITIONS`, default 3) + a per-name cap for the agents (`AGENT_MAX_WEIGHT`)
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
