"""Append the REAL Robinhood Agentic book (total equity, cash, holdings) to state/robin.json
so build_dashboard publishes it as the `Robinhood` competitor. The run-robin skill pulls these
from the MCP after executing (get_portfolio → equity/cash, get_equity_positions → holdings).
Dedupes equity by date; cash/holdings/trades overwrite (latest snapshot of the book).

    python3 tools/record_robin.py <YYYY-MM-DD> <equity> <cash> [trade_count] [--holdings JSON]
    python3 tools/record_robin.py --selfcheck

--holdings is a JSON list: '[{"symbol":"NVDA","qty":0.51,"avg_price":193.06,"filled_at":
"2026-07-02T16:51:06Z"}]' — filled_at (UTC, from the order's last_transaction_at) is REQUIRED
for correct marks: the dashboard refuses to price a holding off a daily close older than its
fill (an intraday buy marked to yesterday's close reads as a phantom gain/loss). The first
recorded equity is the book's origin (the funded amount); build_dashboard rebases the curve to
the shared display origin like every other competitor. Unlike me.json (the private individual
account), this IS the bots' own book, so state/robin.json is committed — real $, holdings and
trades are public; the site just renders them scaled to the display notional.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "robin.json")
ALLOC = os.path.join(ROOT, "state", "robin_alloc.json")


def record(date, equity, cash, trades=None, holdings=None, path=PATH):
    data = json.load(open(path)) if os.path.exists(path) else {"equity": []}
    eq = {d: v for d, v in data.get("equity", [])}
    eq[date] = round(float(equity), 2)  # same date overwrites — re-running a run-robin is safe
    data["equity"] = sorted([d, v] for d, v in eq.items())
    data["cash"] = round(float(cash), 2)
    if trades is not None:
        data["trades"] = int(trades)
    if holdings is not None:
        data["holdings"] = holdings
    data["updated"] = date
    # Stamp the allocation in force, for provenance on the dashboard.
    if os.path.exists(ALLOC):
        data["alloc"] = {a: w for a, w in json.load(open(ALLOC)).get("alloc", {}).items() if w}
    json.dump(data, open(path, "w"), indent=2)
    return data


def main(argv):
    date, equity, cash = argv[0], argv[1], argv[2]
    rest = argv[3:]
    holdings = None
    if "--holdings" in rest:
        i = rest.index("--holdings")
        holdings = json.loads(rest[i + 1])
        rest = rest[:i] + rest[i + 2:]
    trades = int(rest[0]) if rest else None
    record(date, equity, cash, trades, holdings)
    print(f"recorded robin {date} equity={equity} cash={cash}"
          + (f" trades={trades}" if trades is not None else "")
          + (f" holdings={len(holdings)}" if holdings is not None else ""))


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "robin.json")
        record("2026-06-29", 100.0, 40.0, trades=2,
               holdings=[{"symbol": "NVDA", "qty": 0.3, "avg_price": 193.0}], path=p)
        d = record("2026-06-30", 101.5, 41.0, path=p)  # same file, new day, holdings kept
        assert d["equity"] == [["2026-06-29", 100.0], ["2026-06-30", 101.5]], d["equity"]
        assert d["cash"] == 41.0 and d["trades"] == 2 and len(d["holdings"]) == 1, d
        print("record_robin ok", d["equity"])
    else:
        main(sys.argv[1:])
