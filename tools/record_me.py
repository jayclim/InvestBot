"""Append today's REAL total portfolio equity (and optionally the filled-trade COUNT) to
state/me.json (gitignored). During a tick the agent pulls these from the Robinhood MCP
(get_portfolio for equity, get_equity_orders for the count) and records them here; only the
rebased/normalized curve + the trade count are ever published (see build_dashboard.me_competitor).
The actual trades — symbols, dates, sizes, prices — are never written here or committed.
Dedupes equity by date; the trade count is a single cumulative number that overwrites.

    python tools/record_me.py <YYYY-MM-DD> <equity> [trade_count]
    python tools/record_me.py --selfcheck
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "me.json")


def record(date, equity, trades=None, path=PATH):
    data = json.load(open(path)) if os.path.exists(path) else {"equity": []}
    eq = {d: v for d, v in data.get("equity", [])}
    eq[date] = round(float(equity), 2)  # same date overwrites — re-running a tick is safe
    data["equity"] = sorted([d, v] for d, v in eq.items())
    if trades is not None:
        data["trades"] = int(trades)  # cumulative filled-order count (just a number, not the trades)
    json.dump(data, open(path, "w"), indent=2)
    return data


def _selfcheck():
    import tempfile
    p = tempfile.mktemp(suffix=".json")
    record("2026-06-25", 1000, path=p)
    record("2026-06-26", 1010, trades=4, path=p)
    record("2026-06-26", 1020, path=p)  # dedupe by date; trades preserved when omitted
    d = json.load(open(p))
    assert d["equity"] == [["2026-06-25", 1000.0], ["2026-06-26", 1020.0]], d
    assert d["trades"] == 4, d
    os.remove(p)
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        _selfcheck()
    elif len(sys.argv) in (3, 4):
        record(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
        print("recorded", *sys.argv[1:])
    else:
        print(__doc__)
        sys.exit(1)
