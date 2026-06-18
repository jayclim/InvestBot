"""Convert raw robinhood-trading get_equity_historicals JSON dump(s) into
data/snapshot.json (the format the engine reads).

    python tools/ingest_rh.py <raw_rh_file.json> [more_files...]

Interpolated gap-fill bars are dropped. Safe to pass several files (e.g. when the
universe was fetched in chunks); duplicate dates per symbol are de-duped.
"""
import json
import os
import sys


def ingest(paths):
    snap = {}
    for p in paths:
        raw = json.load(open(p))
        for r in raw["data"]["results"]:
            sym = r["symbol"]
            out = snap.setdefault(sym, [])
            seen = {b["date"] for b in out}
            for b in r["bars"]:
                if b.get("interpolated"):
                    continue
                d = b["begins_at"][:10]
                if d in seen:
                    continue
                seen.add(d)
                out.append({
                    "date": d,
                    "open": float(b["open_price"]),
                    "high": float(b["high_price"]),
                    "low": float(b["low_price"]),
                    "close": float(b["close_price"]),
                    "volume": float(b["volume"]),
                })
    for s in snap:
        snap[s].sort(key=lambda x: x["date"])
    return snap


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python tools/ingest_rh.py <raw_rh_file.json> [...]")
        sys.exit(1)
    os.makedirs("data", exist_ok=True)
    snap = ingest(sys.argv[1:])
    with open("data/snapshot.json", "w") as f:
        json.dump(snap, f)
    print(f"wrote data/snapshot.json: {len(snap)} symbols, "
          f"{sum(len(v) for v in snap.values())} bars")
