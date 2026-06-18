---
name: financial-analyst
description: Produce the bake-off's deep-research analyst report using Anthropic's Claude for Financial Services (equity-research) methodology, written to state/analyst.json with portfolio target weights. Use during a tick's analyst step, or when the user says "run the analyst" / "financial analyst".
---

# Financial-services analyst → state/analyst.json

This is the bake-off's research analyst, run with the **Claude for Financial Services**
equity-research methodology instead of ad-hoc research. It produces a research-grounded
portfolio (target weights) for the analyst's $100 paper book.

## Relationship to the official plugin
The official agents live in the `anthropics/financial-services` marketplace and install via
(user action, on any paid plan):
```
claude plugin marketplace add anthropics/financial-services
claude plugin install equity-research@claude-for-financial-services
claude plugin install financial-analysis@claude-for-financial-services
```
- **If those plugins are installed**, use their skills directly: `/screen` (idea sourcing),
  `/sector` (industry landscape), `/comps` (trading multiples), `/catalysts` (upcoming events),
  `/thesis` (maintain/track theses). Lean on them for each step below.
- **If not installed**, follow the same methodology manually (steps below) — the workflow is the value.
- **Data caveat:** the official agents shine with paid-vendor MCP connectors (FactSet, S&P Capital IQ,
  Morningstar, …). This project does NOT have those. Use **Robinhood fundamentals/historicals + web_search**
  as the data layer. Say so in the report. Don't fabricate vendor data.

## What the official agents will NOT do (the bridge)
Per Anthropic, these agents draft research for human review — they **do not make investment
recommendations or execute trades**. Forming the portfolio (target weights) is THIS project's
layer, clearly labelled as such. Never place real orders.

## Methodology (equity-research workflow → portfolio)
Operate over `cfg.UNIVERSE` (the ~100-name list). Produce a concentrated book.
1. **Screen / idea-source (`/screen`)** — narrow the universe to a handful of candidates using
   momentum, relative strength, and valuation from `data/snapshot.json` + Robinhood fundamentals.
2. **Sector & macro (`/sector`)** — read the current regime (Fed path, rates, energy, key sector news)
   via `web_search`; decide which sleeves to favor/avoid.
3. **Fundamentals & comps (`/comps`)** — for the finalists, pull Robinhood fundamentals (P/E, growth,
   52-wk range, margins where available) and compare against peers. Note valuation vs. growth.
4. **Catalysts (`/catalysts`)** — flag upcoming earnings/events that could move each finalist.
5. **Thesis & risk (`/thesis`)** — write a one-paragraph thesis per pick and the risks that invalidate it.
6. **Portfolio construction (the bridge)** — translate into **target weights** (fractions of equity;
   the remainder is cash). Respect risk: keep a sensible cash buffer in a hostile regime, cap any single
   name (≤ `cfg.AGENT_MAX_WEIGHT`), and prefer 2–5 names. Multiple positions are expected.

## Write `state/analyst.json`
Same schema as before, plus a `framework` field marking the methodology. Required keys:
`date`, `as_of`, `pick` (top conviction), `action`, `sizing`, `confidence` (0–1),
`regime{label,note,source}`, `thesis`, `evidence[{point,source}]`, `risks[]`,
`data_examined[{label,source}]`, **`targets` = {SYMBOL: weight}**, `generated_by`, and:
```
"framework": "Claude for Financial Services — equity-research methodology (/screen, /sector, /comps, /catalysts, /thesis). Data: Robinhood fundamentals + web_search (no paid-vendor MCP connectors)."
```
Keep every evidence `source` a real link or a named data source. The dashboard renders `framework`
on the analyst card as provenance.

## After writing
Return to the tick flow (`run_agents.py` reads `state/analyst.json` for the analyst's targets).
This skill only writes the report — it does not move money or place orders.
