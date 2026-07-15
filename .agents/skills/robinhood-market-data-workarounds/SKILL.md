---
name: robinhood-market-data-workarounds
description: Use only within the Stocks/robinhood InvestBot paper-trading project when a daily tick or analysis run needs current-day price bars or bulk historical bars via the Robinhood MCP — e.g. "run today's tick," "refresh the market snapshot," "pull historicals for the universe." Covers the settled-daily-bar evening lag, chunking historicals to stay under the MCP's per-call symbol limit and the tool's output-token cap, and checking whether a new trading session actually exists before spending a paid tick. Not for other brokers/data providers or other projects — this is specific to Robinhood MCP's observed behavior in this repo.
---

# Robinhood market-data workarounds (InvestBot)

This skill applies only to the Stocks/robinhood InvestBot project; if approved, it would be installed at that repo's `.Codex/skills/`, not as a global skill.

## Required inputs / preconditions

- Working inside the Stocks/robinhood InvestBot paper-trading project.
- About to run the daily tick, refresh the price snapshot, or pull bulk historicals for the trading universe via the Robinhood MCP.
- Paper-trading mode only — this skill never places or assumes a real order; the real-money path is a separate, explicitly-gated skill.

## Boundaries

- Paper-trading data-fetch/aggregation only. Never place a real order from this skill's workflow.
- Before spending a paid tick (LLM/agent cost), confirm a new trading session or bar actually exists — don't re-run the full paid pipeline against unchanged prices.
- If a fetch is incomplete or ambiguous, surface that to the user rather than guessing or averaging over the gap.
- **Data handling (financially sensitive in aggregate):**
  - Do not include account values, position sizes, cost basis, or dollar P&L in any output this skill produces or summarizes — that belongs in the project's own dashboard/standings artifacts, not in ad hoc chat output or logs.
  - Do not include account identifiers, credentials, or any `[REDACTED-*]`-style values in outputs.
  - Never fabricate or hold over a bar price to paper over a lagging or missing feed — aggregate from real fetched data only (see workflow), and say explicitly when a fetch came back incomplete rather than silently filling gaps.
  - Keep numeric examples in any documentation generic (e.g. "the universe" or "a chunk of symbols") rather than citing specific account-linked figures.

## Shortest reliable workflow

1. **Check whether a new session actually exists before running a full paid tick.** If it's pre-market, a weekend, or a holiday with no new settled bar, a full tick would just re-decide on unchanged prices at real cost — offer a cheaper alternative instead of running the expensive path by default. That alternative is a **queue-only re-plan**: run `python3 run_agents.py --fill-mode queue` (with the usual `--mirofish-tier` choice), which re-runs the tick pipeline off fresh news but forces every agent's resulting orders to queue for the next session's open instead of filling instantly, rather than assuming a new settled price bar exists.
2. **Pull day-interval bars in chunks** — the MCP caps historicals at a small number of symbols per call, so a full universe requires multiple chunked calls, not one bulk request.
3. **If the daily bar is still lagging after market close** (a known behavior — the settled day bar can lag into the evening), fall back to fetching minute-interval bars for the current session (also chunked) and aggregate them client-side into a single OHLCV bar per symbol, rather than waiting on or assuming the lagging daily feed.
4. **Expect both day- and minute-interval fetches across the full universe to exceed the tool's max-output-token limit.** Treat truncation as the expected case, not an error: read the redirected saved-file result and reconstruct from it via `tools/ingest_rh.py` (pass the saved JSON file path(s) as arguments; it writes `data/snapshot.json`) instead of relying on inline tool output. Ask explicitly for key figures to be quoted verbatim when re-reading a saved result, since a summary can drop the number you need.
5. **Timestamp every fill.** When recording a new position, store the fill's timestamp and refuse to mark that position to a daily close bar dated earlier than the fill — marking a freshly-filled position to a stale prior-day close produces phantom gain/loss on the standings/dashboard.

## Validation

- After rebuilding the snapshot, confirm the resulting symbol count and bar count match the target universe — a chunked fetch can silently drop a chunk without an explicit count check.
- Before trusting an aggregated same-day bar, confirm it was built from real fetched minute bars for that session, not a stale carried-over close.
- If a displayed gain/loss looks implausible, check whether the position's fill timestamp predates the bar currently used to mark it.

## Recovery

- A chunked fetch returns fewer symbols/bars than expected → re-fetch the specific missing chunk explicitly; don't assume the incomplete result is complete.
- The daily bar is confirmed stale after close → switch to the minute-bar aggregation path rather than proceeding on the stale value or blocking the tick entirely.
- A tick would burn cost against an unchanged session → surface the cheaper queue-only/skip alternative to the user rather than deciding unilaterally to run (or skip) the full paid pipeline.
- Gain/loss looks wrong on the dashboard → check fill timestamps against the bar used for marking before assuming a pricing-data bug elsewhere.
