"""Aggregate raw robinhood-trading minute-bar dump(s) into one daily bar per
symbol and append/replace it in data/snapshot.json — for evening ticks, when
the settled `day` bar still reads the prior session.

    python tools/aggregate_intraday.py <date> <minute_file.json> [...] \
        [--fundamentals <fundamentals_file.json> ...]

Summed minute volume badly undercounts the consolidated total (auction and
off-exchange prints are excluded), which suppresses volume-confirmed breakout
signals. Pass the same tick's get_equity_fundamentals dump(s) and each bar's
volume is taken from the fundamentals session volume instead; names without a
matching fundamentals row fall back to the minute sum (with a warning). The
next normal `day` refresh overwrites the bar with the settled one either way.
"""
import json
import sys

SNAPSHOT = "data/snapshot.json"


def load_results(paths):
    for p in paths:
        for r in json.load(open(p))["data"]["results"]:
            yield r


def aggregate(date, minute_paths, fundamentals_paths=(), snap=None):
    snap = snap if snap is not None else json.load(open(SNAPSHOT))
    volumes = {}
    for r in load_results(fundamentals_paths):
        if r.get("market_date") == date and r.get("volume") is not None:
            volumes[r["symbol"]] = float(r["volume"])

    updated, skipped, minute_vol = [], [], []
    for r in load_results(minute_paths):
        sym = r["symbol"]
        bars = [b for b in r["bars"]
                if not b.get("interpolated") and b["begins_at"].startswith(date)]
        series = snap.get(sym)
        if not bars or series is None:
            skipped.append(sym)
            continue
        if sym not in volumes:
            minute_vol.append(sym)
        agg = {
            "date": date,
            "open": float(bars[0]["open_price"]),
            "high": max(float(b["high_price"]) for b in bars),
            "low": min(float(b["low_price"]) for b in bars),
            "close": float(bars[-1]["close_price"]),
            "volume": volumes.get(sym, sum(float(b["volume"]) for b in bars)),
        }
        if series and series[-1]["date"] == date:
            series[-1] = agg
        elif series and series[-1]["date"] > date:
            skipped.append(sym)
            continue
        else:
            series.append(agg)
        updated.append(sym)
    return snap, updated, skipped, minute_vol


def selftest():
    mb = lambda t, o, h, l, c, v: {"begins_at": t, "open_price": o, "high_price": h,
                                   "low_price": l, "close_price": c, "volume": v}
    minute = {"data": {"results": [{"symbol": "AAA", "bars": [
        mb("2026-07-01T13:30:00Z", "10", "11", "9", "10.5", 100),
        mb("2026-07-01T13:31:00Z", "10.5", "12", "10", "11", 200),
        mb("2026-07-01T13:32:00Z", "11", "11", "11", "11", 0),
    ]}, {"symbol": "BBB", "bars": [
        mb("2026-07-01T13:30:00Z", "5", "6", "4", "5.5", 50),
    ]}]}}
    funda = {"data": {"results": [
        {"symbol": "AAA", "market_date": "2026-07-01", "volume": "9999"},
        {"symbol": "BBB", "market_date": "2026-06-30", "volume": "1"},  # stale -> ignored
    ]}}
    import os, tempfile
    with tempfile.TemporaryDirectory() as d:
        mp, fp = os.path.join(d, "m.json"), os.path.join(d, "f.json")
        json.dump(minute, open(mp, "w")); json.dump(funda, open(fp, "w"))
        snap = {"AAA": [{"date": "2026-06-30", "open": 1, "high": 1, "low": 1,
                         "close": 1, "volume": 1}],
                "BBB": [{"date": "2026-07-01", "open": 9, "high": 9, "low": 9,
                         "close": 9, "volume": 9}]}
        snap, updated, skipped, minute_vol = aggregate("2026-07-01", [mp], [fp], snap)
    a, b = snap["AAA"][-1], snap["BBB"][-1]
    assert sorted(updated) == ["AAA", "BBB"] and not skipped
    assert (a["open"], a["high"], a["low"], a["close"]) == (10.0, 12.0, 9.0, 11.0)
    assert a["volume"] == 9999.0, "fundamentals volume should win"
    assert len(snap["AAA"]) == 2, "new date appends"
    assert len(snap["BBB"]) == 1 and b["close"] == 5.5, "same date replaces"
    assert b["volume"] == 50.0 and minute_vol == ["BBB"], "stale fundamentals -> minute sum"
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        sys.exit(0)
    if len(sys.argv) < 3:
        print(next(l.strip() for l in __doc__.splitlines() if "python tools/" in l))
        sys.exit(1)
    args = sys.argv[1:]
    split = args.index("--fundamentals") if "--fundamentals" in args else len(args)
    date, minute_paths, funda_paths = args[0], args[1:split], args[split + 1:]
    snap, updated, skipped, minute_vol = aggregate(date, minute_paths, funda_paths)
    with open(SNAPSHOT, "w") as f:
        json.dump(snap, f)
    print(f"aggregated {date} bar for {len(updated)} symbols"
          + (f" · skipped: {','.join(skipped)}" if skipped else "")
          + (f" · minute-sum volume (no fundamentals row): {','.join(minute_vol)}"
             if minute_vol else ""))
