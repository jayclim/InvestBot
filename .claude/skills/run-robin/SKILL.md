---
name: run-robin
description: Execute the funded algorithms on the REAL Robinhood Agentic cash account (••••) — rebalance it toward the blended target weights of the funded paper books, placing real orders with a per-order review→confirm gate. Use when the user says "run robin", "/run-robin", or asks to trade/rebalance the real Agentic book. NOT paper — this places real orders.
---

# Run the funded algorithms on the REAL account (run-robin)

**This places REAL Robinhood orders with REAL money** on the Agentic cash account ••••
(`cfg.AGENTIC_ACCOUNT`, from `.env`). It is the ONLY skill that does — everything else in this
repo is paper. Two hard rails, never skip them:

1. **Per-order confirmation.** Every order goes `review_equity_order` (dry run) → show the user
   the exact orders → wait for an explicit "yes" → `place_equity_order`. Never place an order the
   user has not just confirmed.
2. **Agentic account only.** Orders go to `cfg.AGENTIC_ACCOUNT` (cash, no options). Never the
   individual or Roth account. If `AGENTIC_ACCOUNT` is empty, stop and ask.

Allocation lives in `state/robin_alloc.json` (`{algo: weight}`; only weight > 0 is run). Currently
100% `momentum_breakout`. To change it, edit that file (or the user asks). The real book is published
as the **`Robinhood`** competitor on the dashboard, scaled to the display notional.

**Fresh run, not a mirror.** run-robin reruns the funded strategies' signals on the latest bar
against the REAL account's current positions — it buys names breaking out *now* and sells held names
that hit their exit. It does NOT copy the paper simulation's portfolio. Often there are **no orders**
(nothing breaking out / nothing to exit) — that's a valid run; just record the unchanged book.

## 0. Preconditions
- `state/robin_alloc.json` has at least one funded algo.
- Robinhood MCP connected (`/mcp`); `cfg.AGENTIC_ACCOUNT` set and the account is funded.
- The funded algos' **paper books are current for the session you're trading** (see step 1).

## 1. Make the funded paper books current (reuse if you just ran them)
run-robin mirrors the paper books, so they must reflect the latest session first.
- **If run-agents / tick.py just ran this session, reuse those outputs — do NOT recompute.**
  (Refreshing the snapshot, the analyst report, and the swarm vote all cost money/time; share them.)
- Otherwise, for the funded algos only: refresh `data/snapshot.json` (run-agents step 1), then advance
  just what's funded — `python3 tick.py` for the rule strategies, `python3 run_agents.py` for any funded
  agent. Skip steps for algos with zero allocation.

## 2. Read the real Agentic book (MCP)
- `get_portfolio` for `cfg.AGENTIC_ACCOUNT` → `total_value` (real equity) and `cash`.
- `get_equity_positions` for the same account → current holdings (symbol, qty, avg cost).

## 3. Compute the orders (fresh signal run)
```bash
python3 tools/robin_plan.py <real_equity> --positions '<live positions json>'
```
Reruns each funded strategy on the latest bar against the live positions and prints the **order
list** directly — buys (sized POSITION_SIZE_PCT of allocated capital) for fresh breakouts, sells for
held names hitting their exit. `--positions` = the step-2 holdings as
`[{"symbol":..,"qty":..,"avg_price":..}]` (omit when flat). No orders are placed here.

## 4. Must be a REGULAR-HOURS run — you cannot queue these for the open
Momentum sizes ~$20 slots, so orders are **fractional / dollar-based**, and Robinhood has **no
fractional market-on-open** — the MCP rejects fractional/dollar orders outside regular hours, so
they can't rest for the next open. Whole-share orders *could* queue, but at a ~$100 book with $20
slots they'd buy 0 shares of most of the (high-priced) universe and distort the strategy — don't.
So: **run during the 9:30–4 ET session; orders fill immediately at the current price** (a daily
strategy doesn't care about open-vs-midday). If `paper.is_rth()` is False, do NOT place — give the
user the planned list and tell them to rerun during the session.

Also: an **empty** list is common (nothing breaking out / nothing to exit) — then skip to step 6 and
record the unchanged book.

## 5. Present the list → yes / no / edit (the gate)
1. `review_equity_order` (dry run) for each order — pull the estimated fill, fees, buying power.
2. **Show the user a numbered table** of every order: side, symbol, $ (or shares), est. price, and the
   resulting book (holdings + leftover cash). Then ask plainly: **yes / no / edit?**
   - **yes** → `place_equity_order` each, to `cfg.AGENTIC_ACCOUNT`, one at a time.
   - **no** → place nothing; stop. (Still record the unchanged book in step 6 if they want the tick logged.)
   - **edit** → apply their change (drop a name, change a $ amount, add/remove an order), re-run
     `review_equity_order` on what changed, **re-show the updated table, and ask yes/no/edit again.**
     Never place until the final list comes back an explicit **yes**.
3. Place ONLY the orders in the confirmed list. If any rejects (buying power, tradability, halt),
   report it and stop — don't silently retry or substitute.

## 6. Record the book
After the fills (or with no change, if nothing traded), pull the account again and record it so the dashboard updates:
```bash
python3 tools/record_robin.py <session-date> <equity> <cash> [trade_count] --holdings '<json>'
```
`<json>` = the live positions as `[{"symbol":..,"qty":..,"avg_price":..}]`; `trade_count` = cumulative
filled Agentic orders (`get_equity_orders` for that account, `placed_agent: agentic`, count `filled`).
First record sets the book's origin (the funded amount). Real $ stays in `state/robin.json`; only the
scaled curve/holdings publish.

## 7. Rebuild the dashboard
```bash
python3 tools/build_dashboard.py
```
Publishes the `Robinhood` competitor (scaled, with the real-money note in its popup). If run-agents
ran this session, this step already happened — rerunning is harmless.

## Rails recap
Real money · Agentic account only · every order reviewed and confirmed before placing · only funded
algos run · reuse run-agents outputs when both run the same session.
