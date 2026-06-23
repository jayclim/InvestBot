"""Run the paper-trading bake-off over a snapshot of daily bars.

    python run.py [data/snapshot.json]

Prints a leaderboard of every strategy's virtual $100 plus end-of-run holdings.
"""
import json
import sys

from bot import config as cfg
from bot.models import Bar
from bot.engine import run_replay
from bot.metrics import summarize
from bot.strategy import MomentumBreakout, MeanReversion, Blended

STRATEGIES = [MomentumBreakout, MeanReversion, Blended]


def load_snapshot(path):
    raw = json.load(open(path))
    snap = {}
    for sym, bars in raw.items():
        if not bars:
            continue
        snap[sym] = [
            Bar(b["date"], b["open"], b["high"], b["low"], b["close"], b["volume"])
            for b in sorted(bars, key=lambda x: x["date"])
        ]
    return snap


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/snapshot.json"
    snap = load_snapshot(path)
    syms = [s for s in snap.keys() if s not in cfg.BENCHMARKS]  # benchmarks ride along but aren't traded
    dates = sorted({b.date for bars in snap.values() for b in bars})

    results = run_replay(snap, STRATEGIES)

    print(f"\nPaper bake-off  |  ${cfg.STARTING_CASH:.0f} each  |  {len(syms)} symbols  "
          f"|  {dates[0]} -> {dates[-1]} ({len(dates)} sessions)")
    print(f"Universe: {', '.join(syms)}\n")

    rows = [(name, summarize(pf, cfg.STARTING_CASH), pf) for name, pf in results.items()]
    rows.sort(key=lambda r: r[1]["final"], reverse=True)

    print(f"{'strategy':22} {'final':>9} {'return':>8} {'maxDD':>7} {'trades':>7} {'win%':>6}")
    print("-" * 64)
    for name, m, _pf in rows:
        print(f"{name:22} {m['final']:>8.2f} {m['return'] * 100:>7.1f}% "
              f"{m['max_dd'] * 100:>6.1f}% {m['trades']:>7} {m['win_rate'] * 100:>5.0f}%")
    print()

    for name, _m, pf in rows:
        if pf.positions:
            held = ", ".join(f"{s}({p.qty:.3f}@{p.avg_price:.2f})" for s, p in pf.positions.items())
            print(f"  {name}: holding {held}; cash ${pf.cash:.2f}")
        else:
            print(f"  {name}: flat; cash ${pf.cash:.2f}")


if __name__ == "__main__":
    main()
