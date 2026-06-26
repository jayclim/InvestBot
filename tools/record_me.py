"""Append today's REAL total portfolio equity to state/me.json (gitignored). During a tick the
agent pulls the value from the Robinhood MCP (get_portfolio) and records it here; only the
rebased, normalized curve is ever published (see build_dashboard.me_competitor). Dedupes by date.

    python tools/record_me.py <YYYY-MM-DD> <equity>
    python tools/record_me.py --selfcheck
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "me.json")


def record(date, equity, path=PATH):
    data = json.load(open(path)) if os.path.exists(path) else {"equity": []}
    eq = {d: v for d, v in data.get("equity", [])}
    eq[date] = round(float(equity), 2)  # same date overwrites — re-running a tick is safe
    data["equity"] = sorted([d, v] for d, v in eq.items())
    json.dump(data, open(path, "w"), indent=2)
    return data["equity"]


def _selfcheck():
    import tempfile
    p = tempfile.mktemp(suffix=".json")
    record("2026-06-25", 1000, p)
    record("2026-06-26", 1010, p)
    record("2026-06-26", 1020, p)  # dedupe: latest value for the date wins
    got = json.load(open(p))["equity"]
    assert got == [["2026-06-25", 1000.0], ["2026-06-26", 1020.0]], got
    os.remove(p)
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        _selfcheck()
    elif len(sys.argv) == 3:
        record(sys.argv[1], sys.argv[2])
        print("recorded", sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
