# Robinhood paper-trading bake-off

A harness for testing several "high-variance but rule-based" strategies against each
other with **fake money**, before risking a real dollar. Each strategy trades its own
virtual $100 over the same universe, so the result is an apples-to-apples leaderboard.

Stdlib-only Python — no installs needed.

## Design

The strategy never knows whether its orders hit a simulator or a real account. That
decoupling is what lets us test now and go live later with the same code.

```
strategy  ->  Signal  ->  engine  ->  Broker
                                       |- PaperBroker     (simulated fills, used now)
                                       |- RobinhoodBroker (wraps MCP place_equity_order, later)
```

- `bot/strategy.py` — the competitors: `momentum_breakout`, `mean_reversion`, `blended_momo_rsi`
- `bot/engine.py` — walk-forward replay, no lookahead, hard stops + circuit breaker
- `bot/portfolio.py` — cash / positions / realized trades / equity curve
- `bot/config.py` — universe, risk limits, signal params (edit me)

## Run it

```bash
python run.py                 # uses data/snapshot.json
python run.py data/snap2.json # or point at another snapshot
```

## Getting data (the honest part)

A standalone process can't reach the `robinhood-trading` MCP tools — those are wired
to the Claude agent. So data arrives **agent-driven**:

1. The agent calls `get_equity_historicals` for the universe and saves the raw JSON.
2. `python tools/ingest_rh.py <raw_file.json> [...]` converts it to `data/snapshot.json`.
3. `python run.py` replays it.

For a live forward test, repeat daily: append the new day's bar, step the engine once.

## Risk controls (the "not gambling" part)

- Hard stop per position (`STOP_LOSS_PCT`, default 15%)
- Max open positions (`MAX_POSITIONS`, default 3)
- Equity circuit breaker (`CIRCUIT_BREAKER_EQUITY`, default $60) halts new buys
- Simulated slippage on every fill so paper results aren't flattering

## Going live (later)

Only after a strategy clears a graduation bar (survived a drawdown, enough trades,
tolerable max DD) do we implement `RobinhoodBroker` against the **Agentic** cash
account `••••` — the only one that accepts agent orders. Note: that account has
**no options** enabled, so this harness is equities/ETFs only unless options are added.
