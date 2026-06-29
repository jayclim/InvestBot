"""Append today's REAL total portfolio equity (and optionally the filled-trade COUNT) to
state/me.json (gitignored). During a tick the agent pulls these from the Robinhood MCP
(get_portfolio for equity, get_equity_orders for the count) and records them here; only the
rebased/normalized curve + the trade count are ever published (see build_dashboard.me_competitor).
The actual trades — symbols, dates, sizes, prices — are never written here or committed.
Dedupes equity by date; the trade count is a single cumulative number that overwrites.

    python tools/record_me.py <YYYY-MM-DD> <equity> [trade_count] [--flow NET]
    python tools/record_me.py --selfcheck

--flow NET is the net EXTERNAL cash moved during the period ending <date>: deposits positive,
withdrawals negative (e.g. you transferred $500 out to your Roth → --flow -500). It is stripped
from the published curve via a time-weighted index (build_dashboard.twr_index), so transferring
money in or out never reads as P&L — only investment return is compared, fair against the
always-fully-invested algos. Cash interest is real return — leave it IN (don't pass it as a flow).
Omit --flow when no transfer happened that period. Pass it every time you move money in or out.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "me.json")


def record(date, equity, trades=None, flow=None, path=PATH):
    data = json.load(open(path)) if os.path.exists(path) else {"equity": []}
    eq = {d: v for d, v in data.get("equity", [])}
    eq[date] = round(float(equity), 2)  # same date overwrites — re-running a tick is safe
    data["equity"] = sorted([d, v] for d, v in eq.items())
    if trades is not None:
        data["trades"] = int(trades)  # cumulative filled-order count (just a number, not the trades)
    if flow is not None:
        flows = data.get("flows", {})
        flows[date] = round(float(flow), 2)  # net external deposit(+)/withdrawal(−) this period
        data["flows"] = flows
    json.dump(data, open(path, "w"), indent=2)
    return data


def _selfcheck():
    import tempfile
    p = tempfile.mktemp(suffix=".json")
    record("2026-06-25", 1000, path=p)
    record("2026-06-26", 1010, trades=4, path=p)
    record("2026-06-26", 1020, path=p)            # dedupe by date; trades preserved when omitted
    record("2026-06-29", 600, flow=-500, path=p)  # withdrew 500 — equity is the real post-transfer value
    d = json.load(open(p))
    assert d["equity"] == [["2026-06-25", 1000.0], ["2026-06-26", 1020.0], ["2026-06-29", 600.0]], d
    assert d["trades"] == 4, d
    assert d["flows"] == {"2026-06-29": -500.0}, d
    os.remove(p)
    print("ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    flow = None
    if "--flow" in args:                          # pull --flow NET out of the positional args
        i = args.index("--flow")
        flow = args[i + 1]
        del args[i:i + 2]
    if args == ["--selfcheck"]:
        _selfcheck()
    elif len(args) in (2, 3):
        record(args[0], args[1], args[2] if len(args) == 3 else None, flow)
        print("recorded", *sys.argv[1:])
    else:
        print(__doc__)
        sys.exit(1)
