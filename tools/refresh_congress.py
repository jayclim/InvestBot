"""Pull congressional trades from a free, daily-updated GitHub mirror — no API key, no Cloudflare.

kadoa-org/congress-trading-monitor parses public STOCK Act disclosures (House Clerk + Senate eFD)
and commits them as static JSON, refreshed daily by GitHub Actions. We read its own per-filer
performance ranking (returns.json) to pick the MOST SUCCESSFUL members of Congress, then collect
those filers' disclosed PURCHASES into state/congress.json. The congress_mirror competitor
(bot.paper.congress_targets) trades on the DISCLOSURE date only — never backfilled to the
(up-to-45-days-earlier) transaction date, which would be the look-ahead cheat.

    python3 tools/refresh_congress.py      # refresh the cache (date-cached: one network pull/day)

Data: public-domain financial-disclosure filings, via the kadoa mirror. Read-only; no money moves.
"""
import datetime as _dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import config as cfg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "congress.json")
RAW = "https://raw.githubusercontent.com/kadoa-org/congress-trading-monitor/main/public/data"


def _get(path):
    req = urllib.request.Request(f"{RAW}/{path}", headers={"User-Agent": "investbot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _is_buy(t):
    return str(t.get("transaction_type", "")).lower().startswith("purchase")


def refresh_congress(path=PATH, today=None, top=None, min_buys=None):
    """Date-cached: one network pull per calendar day, instant reuse after. Returns the cache dict
    {date, leaders, trades}. On any network error, falls back to the existing cache (or an empty
    stub with `error`) so a tick never aborts on the feed being down."""
    today = today or _dt.date.today().isoformat()
    top = top or cfg.CONGRESS_TOP_FILERS
    min_buys = min_buys or cfg.CONGRESS_MIN_SCORED_BUYS
    if os.path.exists(path):
        cached = json.load(open(path))
        if cached.get("date") == today and cached.get("trades") is not None:
            return cached
    try:
        ranked = [f for f in _get("returns.json")
                  if f.get("branch") == "congress" and (f.get("scored_buys") or 0) >= min_buys]
        ranked.sort(key=lambda f: f.get("weighted_excess") or f.get("avg_excess") or 0, reverse=True)
        leaders = ranked[:top]
        trades = []
        for f in leaders:
            try:
                fj = _get(f"filer/{f['id']}.json")
            except Exception:
                continue  # one missing filer file shouldn't sink the whole refresh
            for t in fj.get("trades", []):
                if _is_buy(t) and t.get("ticker") in cfg.UNIVERSE and t.get("filing_date"):
                    trades.append({"filer_id": f["id"], "filer": f.get("full_name"),
                                   "ticker": t["ticker"], "filing_date": t["filing_date"],
                                   "transaction_date": t.get("transaction_date"),
                                   "amount_label": t.get("amount_range_label")})
        out = {"date": today, "asof": _dt.datetime.now().isoformat(timespec="seconds"),
               "source": "kadoa-org/congress-trading-monitor (public-domain STOCK Act filings)",
               "leaders": [{"id": f["id"], "name": f.get("full_name"), "party": f.get("party"),
                            "chamber": f.get("chamber"), "scored_buys": f.get("scored_buys"),
                            "weighted_excess": f.get("weighted_excess")} for f in leaders],
               "trades": trades}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(out, open(path, "w"), indent=0)
        return out
    except Exception as e:
        if os.path.exists(path):
            return json.load(open(path))
        return {"date": today, "leaders": [], "trades": [], "error": str(e)}


def load_congress(path=PATH):
    return json.load(open(path)) if os.path.exists(path) else {"leaders": [], "trades": []}


if __name__ == "__main__":
    c = refresh_congress()
    if c.get("error"):
        print(f"congress: fetch failed ({c['error']}) and no cache to fall back on")
    print(f"congress: {len(c.get('trades', []))} in-universe disclosed buys from "
          f"{len(c.get('leaders', []))} top filers (cached {c.get('date')})")
    for L in c.get("leaders", []):
        print(f"  {(L.get('name') or '?'):26s} {(L.get('party') or '?')}/{(L.get('chamber') or '?'):6s} "
              f"buys={L.get('scored_buys')}  wexcess={L.get('weighted_excess')}")
