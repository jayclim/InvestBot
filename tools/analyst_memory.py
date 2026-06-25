"""Analyst memory: print the analyst's book carried forward from last tick — current holdings
marked vs entry, the last 5 realized trades, performance vs SPY (alpha + Sharpe), last run's thesis
gist + targets, and the prior tick's reflection (the distilled what-worked/what-I'm-changing). The
financial-analyst skill reads this before writing the new report so it UPDATES a thesis instead of
starting cold.

    python3 tools/analyst_memory.py

Read-only. Touches no money and writes nothing.
"""
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run import load_snapshot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "deep_research_analyst"


def _perf(equity_curve, spy_close):
    """Book vs SPY over the book's lifetime and last tick + a rough annualized Sharpe.
    equity_curve: [[date, equity], ...]; spy_close: {date: close}. None if <2 shared dates."""
    ec = [(d, e) for d, e in equity_curve if d in spy_close]
    if len(ec) < 2:
        return None
    (d0, e0), (dp, ep), (dN, eN) = ec[0], ec[-2], ec[-1]
    rets = [ec[i][1] / ec[i - 1][1] - 1 for i in range(1, len(ec))]
    sharpe = (statistics.mean(rets) / statistics.pstdev(rets) * (252 ** 0.5)
              if len(rets) >= 2 and statistics.pstdev(rets) > 0 else None)
    return {"book_all": eN / e0 - 1, "spy_all": spy_close[dN] / spy_close[d0] - 1,
            "alpha_all": (eN / e0) - (spy_close[dN] / spy_close[d0]),
            "book_tick": eN / ep - 1, "spy_tick": spy_close[dN] / spy_close[dp] - 1,
            "alpha_tick": (eN / ep) - (spy_close[dN] / spy_close[dp]),
            "sharpe": sharpe, "n": len(ec)}


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

    perf = _perf(pf.get("equity_curve", []), {b.date: b.close for b in snap.get("SPY", [])})
    if perf:
        out.append("Performance vs SPY (benchmark — grade ALPHA, not raw P&L):")
        out.append(f"  all-time : book {perf['book_all'] * 100:+.1f}%  vs SPY {perf['spy_all'] * 100:+.1f}%"
                   f"  -> alpha {perf['alpha_all'] * 100:+.1f} pts")
        out.append(f"  last tick: book {perf['book_tick'] * 100:+.1f}%  vs SPY {perf['spy_tick'] * 100:+.1f}%"
                   f"  -> alpha {perf['alpha_tick'] * 100:+.1f} pts")
        if perf["sharpe"] is not None:
            out.append(f"  Sharpe (annualized, {perf['n']} sessions — noisy): {perf['sharpe']:.2f}")
        out.append("")

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
    # ponytail: self-check the alpha/Sharpe math on synthetic data before printing the real brief
    _t = _perf([["d0", 100.0], ["d1", 110.0]], {"d0": 100.0, "d1": 105.0})
    assert abs(_t["book_all"] - 0.10) < 1e-9 and abs(_t["alpha_all"] - 0.05) < 1e-9, _t
    assert _perf([["d0", 100.0]], {"d0": 100.0}) is None  # too little shared data
    print(brief())
