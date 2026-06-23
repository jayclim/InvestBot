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

## Step 0 — read your memory (carry the book forward, don't start cold)
You manage a live paper book across ticks. Before researching, read your own history:
```
python3 tools/analyst_memory.py
```
It prints your current holdings marked vs your entry, your last 5 realized trades, last tick's
thesis gist + targets, and your prior `reflection` (the distilled what-worked / what-I'm-changing).
That's recent history + summarized reasoning by design — not the whole trade log or every past
thesis verbatim. If you need the full prior write-up, read `state/analyst.json` directly before you
overwrite it. Use this: **keep conviction where the thesis still holds, cut or resize where it
broke**, and in the new report's `thesis` state what changed since last tick. This is a thesis
*update*, not a cold re-pick.

## Methodology (equity-research workflow → portfolio)
Operate over `cfg.UNIVERSE` (the ~100-name list). **Run this deeply** — it is the bake-off's
deep-research competitor, so screen the WHOLE universe (not a glance), pull real Robinhood
fundamentals on every finalist, and back each pick with a current catalyst from `web_search`.
Produce a concentrated book.

**Anti-bias — randomize the order first.** Order bias is real: screened in config order, the same
names lead every tick. Shuffle the universe before you look and screen in that order, so position
never decides conviction:
```
python3 -c "import random,json;from bot import config as c;u=list(c.UNIVERSE);random.shuffle(u);print(json.dumps(u))"
```
1. **Screen / idea-source (`/screen`)** — over the shuffled universe, narrow to a handful of
   candidates using momentum, relative strength, and valuation from `data/snapshot.json` +
   Robinhood fundamentals.
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
`data_examined[{label,source}]`, **`targets` = {SYMBOL: weight}**,
**`rationale` = {SYMBOL: "<why THIS name and this weight>"}** — one entry per name in `targets`.
The dashboard renders each trade with its own reasoning: a one-liner shows inline under the trade,
a fuller deep-dive paragraph collapses into an expandable dropdown. Write as much as each name
warrants (a short note for an obvious add, a paragraph for the anchor) — `generated_by`,
**`reflection`** (see below), and:
```
"framework": "Claude for Financial Services — equity-research methodology (/screen, /sector, /comps, /catalysts, /thesis). Data: Robinhood fundamentals + web_search (no paid-vendor MCP connectors)."
```
Keep every evidence `source` a real link or a named data source. The dashboard renders `framework`
on the analyst card as provenance.

### `reflection` — grade the prior tick before you re-pick (the learning loop)
You have memory, so use it. From `python3 tools/analyst_memory.py` (last thesis, targets, risks, and
the realized P&L of every closed trade), write an honest retrospective on the PRIOR tick — what the
trades actually did, what the thesis got right, and what it missed. Ground every claim in a real
number or trade; don't invent outcomes. This block drives the new picks: keep conviction where the
read was correct, cut/resize where it broke. Schema:
```
"reflection": {
  "as_of": "<the prior tick's date you're grading>",
  "looking_back": "<2-4 sentences: what you held/traded last tick and what the realized P&L did>",
  "worked":  ["<a call the data vindicated - name the trade/number>", ...],
  "missed":  ["<what went wrong or was overlooked - a risk that bit, a name you under/over-sized>", ...],
  "adjustment": "<the one concrete change you're making THIS tick because of the above>"
}
```
First tick (no prior book): set `looking_back` to "First tick - no prior trades to grade yet." and
leave the lists empty. The dashboard renders this as the analyst's "Looking back" block.

## After writing
Return to the tick flow (`run_agents.py` reads `state/analyst.json` for the analyst's targets).
This skill only writes the report — it does not move money or place orders.
