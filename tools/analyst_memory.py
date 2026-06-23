"""Analyst memory: print the analyst's book carried forward from last tick — current holdings
marked vs entry, the last 5 realized trades, last run's thesis gist + targets, and the prior
tick's reflection (the distilled what-worked/what-I'm-changing). The financial-analyst skill reads
this before writing the new report so it UPDATES a thesis instead of starting cold.

    python3 tools/analyst_memory.py

Read-only. Touches no money and writes nothing.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run import load_snapshot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "deep_research_analyst"


def brief():
    state_path = os.path.join(ROOT, "state", "agent_state.json")
    if not os.path.exists(state_path):
        return "Analyst memory: no history yet — first tick, start fresh."
    pf = json.load(open(state_path)).get("portfolios", {}).get(NAME)
    if not pf:
        return "Analyst memory: no analyst book yet — first tick, start fresh."

    snap = load_snapshot(os.path.join(ROOT, "data", "snapshot.json"))
    prices = {s: bars[-1].close for s, bars in snap.items() if bars}

    equity = pf["cash"] + sum(p["qty"] * prices.get(p["symbol"], p["avg_price"]) for p in pf["positions"])
    out = ["# Analyst memory — your book carried forward from last tick\n",
           f"Equity ${equity:.2f} · cash ${pf['cash']:.2f} · started $100.00 "
           f"({(equity / 100 - 1) * 100:+.1f}% all-time)\n"]

    if pf["positions"]:
        out.append("Holdings (mark vs your entry):")
        for p in pf["positions"]:
            px = prices.get(p["symbol"], p["avg_price"])
            pnl = (px / p["avg_price"] - 1) * 100
            out.append(f"  {p['symbol']:6s} entry {p['avg_price']:.2f} -> now {px:.2f}  "
                       f"{pnl:+.1f}%  (since {p['entry_date']})")
    else:
        out.append("Holdings: flat (all cash).")

    sells = [t for t in pf.get("trades", []) if t["side"] == "sell"]
    if sells:
        out.append("\nRecent closed trades (realized P&L):")
        for t in sells[-5:]:
            out.append(f"  {t['date']} {t['symbol']:6s} {t['reason']:26s} P&L ${t['pnl']:+.2f}")

    ap = os.path.join(ROOT, "state", "analyst.json")
    if os.path.exists(ap):
        prior = json.load(open(ap))
        # ponytail: feed the gist (first 2 sentences) of last thesis, not the whole essay — the
        # distilled "what worked / what I'm changing" lives in the reflection below.
        thesis = prior.get("thesis", "-") or "-"
        gist = " ".join(re.split(r"(?<=[.?!])\s+", thesis)[:2])
        out.append(f"\nLast thesis gist ({prior.get('date', '?')}): {gist}")
        out.append(f"Last targets: {prior.get('targets', {})}")
        ref = prior.get("reflection") or {}
        if ref:
            out.append("\nYour reflection on last tick (carry the lessons forward):")
            if ref.get("looking_back"):
                out.append(f"  {ref['looking_back']}")
            for w in ref.get("worked", []):
                out.append(f"  + nailed: {w}")
            for miss in ref.get("missed", []):
                out.append(f"  - missed: {miss}")
            if ref.get("adjustment"):
                out.append(f"  => adjusting: {ref['adjustment']}")
        elif prior.get("risks"):
            out.append("Risks you flagged: " + "; ".join(prior["risks"]))

    out.append("\nUpdate the thesis: keep conviction where it still holds, cut or resize where it "
               "broke, and in the new report say what changed since last tick.")
    return "\n".join(out)


if __name__ == "__main__":
    print(brief())
