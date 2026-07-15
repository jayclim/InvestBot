"""Convert raw robinhood-trading get_equity_historicals JSON dump(s) into
data/snapshot.json (the format the engine reads).

    python tools/ingest_rh.py <raw_rh_file.json> [more_files...]

Interpolated gap-fill bars are dropped. Safe to pass several files (e.g. when the
universe was fetched in chunks); duplicate dates per symbol are de-duped.
Backfill JSON files (*_backfill.json) are auto-merged; integrity checks warn on
short histories and unflagged interpolation (flat runs).
"""
import json
import os
import sys
import glob


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


def merge_backfills(snap, data_dir="data"):
    for path in sorted(glob.glob(os.path.join(data_dir, "*_backfill.json"))):
        sym = os.path.basename(path).replace("_backfill.json", "").upper()
        bars = json.load(open(path))
        out = snap.setdefault(sym, [])
        seen = {b["date"] for b in out}
        added = 0
        for b in bars:
            if b["date"] not in seen:
                out.append(b)
                seen.add(b["date"])
                added += 1
        out.sort(key=lambda x: x["date"])
        if added > 0:
            print(f"merged {path} into {sym}: +{added} bars")


def check_integrity(snap):
    warnings = []
    bar_counts = [len(bars) for bars in snap.values()]
    if not bar_counts:
        return warnings
    median = sorted(bar_counts)[len(bar_counts) // 2]
    short_threshold = 0.8 * median
    for sym, bars in snap.items():
        if len(bars) < short_threshold:
            msg = f"WARNING: {sym} has {len(bars)} bars vs median {median} — short history (Robinhood interpolated bars dropped?); consider data/{sym.lower()}_backfill.json"
            warnings.append(msg)
            print(msg, file=sys.stderr)
    for sym, bars in snap.items():
        i = 0
        while i < len(bars):
            flat_start = i
            while i < len(bars) and (bars[i]["volume"] == 0 or bars[i]["high"] == bars[i]["low"]):
                i += 1
            run_len = i - flat_start
            if run_len >= 3:
                msg = f"WARNING: {sym} has {run_len}-bar flat run ({bars[flat_start]['date']}—{bars[i-1]['date']}) — possible unflagged interpolation"
                warnings.append(msg)
                print(msg, file=sys.stderr)
            i += 1
    return warnings


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selfcheck":
        import tempfile
        snap = {
            "AAPL": [
                {"date": "2026-01-01", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
                {"date": "2026-01-02", "open": 100.5, "high": 102, "low": 100, "close": 101.5, "volume": 1100},
                {"date": "2026-01-03", "open": 101.5, "high": 103, "low": 101, "close": 102.5, "volume": 1200},
            ],
            "SHORT": [{"date": "2026-01-01", "open": 50, "high": 51, "low": 49, "close": 50.5, "volume": 500}],
            "FLAT": [
                {"date": "2026-01-01", "open": 75, "high": 75, "low": 75, "close": 75, "volume": 0},
                {"date": "2026-01-02", "open": 75, "high": 75, "low": 75, "close": 75, "volume": 0},
                {"date": "2026-01-03", "open": 75, "high": 75, "low": 75, "close": 75, "volume": 0},
                {"date": "2026-01-04", "open": 76, "high": 77, "low": 75.5, "close": 76.5, "volume": 500},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            backfill_path = os.path.join(tmpdir, "aapl_backfill.json")
            json.dump([
                {"date": "2025-12-31", "open": 99, "high": 100, "low": 98, "close": 99.5, "volume": 900},
                {"date": "2026-01-02", "open": 100.5, "high": 102, "low": 100, "close": 101.5, "volume": 1100},
            ], open(backfill_path, "w"))
            merge_backfills(snap, tmpdir)
            assert len(snap["AAPL"]) == 4, f"expected 4 AAPL bars after merge, got {len(snap['AAPL'])}"
            assert snap["AAPL"][0]["date"] == "2025-12-31", "backfill bar not added"
            assert snap["AAPL"][1]["date"] == "2026-01-01", "order broken"
        warnings = check_integrity(snap)
        assert len(warnings) >= 2, f"expected at least 2 warnings, got {len(warnings)}: {warnings}"
        assert any("SHORT" in w for w in warnings), "SHORT not flagged"
        assert any("FLAT" in w for w in warnings), "FLAT not flagged"
        print("selfcheck ok")
        sys.exit(0)
    if len(sys.argv) < 2:
        print("usage: python tools/ingest_rh.py <raw_rh_file.json> [...]")
        sys.exit(1)
    os.makedirs("data", exist_ok=True)
    snap = ingest(sys.argv[1:])
    merge_backfills(snap)
    check_integrity(snap)
    with open("data/snapshot.json", "w") as f:
        json.dump(snap, f)
    print(f"wrote data/snapshot.json: {len(snap)} symbols, "
          f"{sum(len(v) for v in snap.values())} bars")
