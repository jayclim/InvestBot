"""One forward paper-test tick. Advances each strategy's persistent $100 portfolio
through any NEW trading days in the snapshot since the last tick, then saves state.

    python tick.py [data/snapshot.json]

First run initializes state FLAT as of the snapshot's latest date (clean start,
no backfill) and trades nothing. Each later day with a new completed bar trades.

Daily workflow (agent-driven): the agent refreshes data/snapshot.json from the
robinhood-trading MCP, then runs this. State lives in state/paper_state.json.
"""
import sys

from bot import config as cfg
from bot.broker import PaperBroker
from bot.engine import step_day, index_snapshot
from bot.metrics import summarize
from bot.state import load_state, save_state
from bot.strategy import MomentumBreakout, MeanReversion, Blended
from run import load_snapshot

REGISTRY = {c.name: c for c in (MomentumBreakout, MeanReversion, Blended)}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/snapshot.json"
    snap = load_snapshot(path)
    all_dates, by_sym_date = index_snapshot(snap)
    seed_last = all_dates[-1]

    last_date, portfolios = load_state(list(REGISTRY), cfg.STARTING_CASH, seed_last)
    broker = PaperBroker(cfg.SLIPPAGE_BPS)

    new_dates = [d for d in all_dates if d > last_date]
    for d in new_dates:
        di = all_dates.index(d)
        for name, pf in portfolios.items():
            step_day(pf, REGISTRY[name](), snap, by_sym_date, all_dates, di, broker)

    save_state(all_dates[-1], portfolios)

    if not new_dates:
        print(f"Forward test armed/flat as of {all_dates[-1]}. "
              f"No new completed sessions since last tick ({last_date}).")
    else:
        print(f"Processed {len(new_dates)} new session(s): {new_dates[0]} -> {new_dates[-1]}")
    print()

    rows = [(n, summarize(pf, cfg.STARTING_CASH), pf) for n, pf in portfolios.items()]
    rows.sort(key=lambda r: r[1]["final"], reverse=True)
    print(f"{'strategy':22} {'equity':>9} {'return':>8} {'maxDD':>7} {'trades':>7}")
    print("-" * 56)
    for n, m, _pf in rows:
        print(f"{n:22} {m['final']:>8.2f} {m['return']*100:>7.1f}% {m['max_dd']*100:>6.1f}% {m['trades']:>7}")
    for n, _m, pf in rows:
        if pf.positions:
            held = ", ".join(f"{s}({p.qty:.3f}@{p.avg_price:.2f})" for s, p in pf.positions.items())
            print(f"  {n}: holding {held}; cash ${pf.cash:.2f}")
        else:
            print(f"  {n}: flat; cash ${pf.cash:.2f}")


if __name__ == "__main__":
    main()
