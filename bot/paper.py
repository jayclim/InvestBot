"""Paper accounts for the AI agents (analyst + swarm).

Each agent gets its own $100 book. On every run it can buy multiple names and sell
multiple names — we rebalance the book toward a set of target weights at current
prices, with slippage. State persists in state/agent_state.json so the forward
track record accrues across runs. No real money touches this.
"""
import datetime as _dt
import json
import os
from zoneinfo import ZoneInfo

from bot import config as cfg
from bot.portfolio import Portfolio
from bot.broker import PaperBroker
from bot.state import _pf_to_dict, _pf_from_dict

_ET = ZoneInfo("America/New_York")


def is_rth(now=None):
    """True if NOW is within US regular trading hours (Mon-Fri 09:30-16:00 ET) — when a run
    fills instantly. Outside it, orders queue for the next session's open.
    ponytail: no holiday calendar — a market holiday on a weekday reads as open; add a US-holiday
    set here if that edge ever matters."""
    now = (now or _dt.datetime.now(_ET)).astimezone(_ET)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    mins = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= mins < 16 * 60

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "agent_state.json")


def load_agents(names):
    """Returns (last_date, {name: Portfolio}, {name: [pending order, ...]})."""
    if os.path.exists(PATH):
        raw = json.load(open(PATH))
        pfs = {}
        for n in names:
            pfs[n] = (_pf_from_dict(n, raw["portfolios"][n])
                      if n in raw.get("portfolios", {}) else Portfolio(cfg.STARTING_CASH, n))
        return raw.get("last_date"), pfs, raw.get("pending", {})
    return None, {n: Portfolio(cfg.STARTING_CASH, n) for n in names}, {}


def save_agents(date, pfs, pending=None):
    """Persist books + open (queued) orders. `pending=None` preserves whatever is on disk, so a
    caller that only touches the books never clobbers another step's queued orders."""
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    if pending is None:
        pending = json.load(open(PATH)).get("pending", {}) if os.path.exists(PATH) else {}
    json.dump({"last_date": date, "portfolios": {n: _pf_to_dict(pf) for n, pf in pfs.items()},
               "pending": pending}, open(PATH, "w"), indent=0)


def risk_for(name):
    """(stop_pct, breaker_equity) for an agent — per-agent override (cfg.AGENT_RISK) falling
    back to the global defaults. A None value disables that control."""
    r = cfg.AGENT_RISK.get(name, {})
    return r.get("stop_pct", cfg.STOP_LOSS_PCT), r.get("breaker_equity", cfg.CIRCUIT_BREAKER_EQUITY)


def plan_orders(pf, targets, prices, label, stop_pct=cfg.STOP_LOSS_PCT,
                breaker_equity=cfg.CIRCUIT_BREAKER_EQUITY, limits=None):
    """Compute the orders that move the book toward target weights {symbol: fraction-of-equity},
    WITHOUT mutating it — sells (stops, exits, trims) first, then buys, the same sequence a fill
    would apply. Each order is a dict; `limits` {symbol: price} tags that name's order a limit
    (else market-on-open when queued / instant when filled in RTH).

    Same two risk controls the rule engine applies (engine.step_day), per-agent via risk_for;
    pass None to opt a strategy out when a control doesn't fit it:
      stop_pct       — force-exit any held name down > this fraction from avg cost, and don't
                       re-buy it this tick (None = no stop, e.g. a mean-reversion book).
      breaker_equity — halt NEW buys while equity < this (None = no breaker; still trims/sells).
    """
    limits = limits or {}
    targets = {s: min(w, cfg.AGENT_MAX_WEIGHT) for s, w in targets.items() if w > 0 and s in prices}
    held = {s: p.qty for s, p in pf.positions.items()}
    avg = {s: p.avg_price for s, p in pf.positions.items()}
    cash = pf.cash
    orders = []

    def _o(sym, side, reason, dollars=None, qty=None):
        return {"symbol": sym, "side": side, "kind": "limit" if sym in limits else "moo",
                "limit": limits.get(sym), "dollars": dollars, "qty": qty, "reason": reason}

    # 0) hard stop: bail out of anything that has fallen past the stop before re-voting
    if stop_pct:
        for s in list(held):
            px = prices.get(s)
            if px and px <= avg[s] * (1 - stop_pct):
                orders.append(_o(s, "sell", f"{label}: stop -{stop_pct*100:.0f}%", qty=held[s]))
                cash += held[s] * px
                held.pop(s); targets.pop(s, None)  # stopped out -> don't re-buy this tick

    # 1) exit anything no longer targeted
    for s in list(held):
        if s not in targets:
            px = prices.get(s, avg[s])
            orders.append(_o(s, "sell", f"{label}: exit", qty=held[s]))
            cash += held[s] * px
            held.pop(s)

    # 2) buy / trim toward each target weight (trims first, then buys — sorted by weight)
    equity = pf.equity(prices)
    halt_buys = breaker_equity is not None and equity < breaker_equity
    for s, w in sorted(targets.items(), key=lambda kv: kv[1]):
        target_dollars = equity * w
        cur_dollars = held.get(s, 0.0) * prices[s]
        diff = target_dollars - cur_dollars
        if diff > 1.0 and cash > 1.0 and not halt_buys:
            spend = min(diff, cash)
            orders.append(_o(s, "buy", f"{label}: buy {w*100:.0f}%", dollars=spend))
            cash -= spend
        elif diff < -1.0 and s in held:
            qty = min(held[s], (-diff) / prices[s])
            orders.append(_o(s, "sell", f"{label}: trim", qty=qty))
    return orders


def _sell_qty(o, pf):
    if o["qty"] is not None:
        return o["qty"]
    pos = pf.positions.get(o["symbol"])
    return pos.qty if pos else 0.0


def execute_orders(pf, orders, prices, date, broker):
    """Fill a planned order list instantly at `prices` (with slippage) — the in-hours path."""
    for o in orders:
        px = prices.get(o["symbol"])
        if px is None:
            continue
        if o["side"] == "buy":
            pf.buy(o["symbol"], broker.buy_price(px), min(o["dollars"], pf.cash), date, o["reason"])
        else:
            pf.sell(o["symbol"], broker.sell_price(px), date, o["reason"], qty=_sell_qty(o, pf))


def _fill_price(o, bar):
    """The price a queued order fills at in `bar`, or None if a limit didn't trade through.
    MOO fills at the open; a buy limit needs the session low <= limit, a sell limit high >= limit."""
    if o["kind"] != "limit" or o["limit"] is None:
        return bar.open
    lim = o["limit"]
    if o["side"] == "buy":
        return min(bar.open, lim) if bar.low <= lim else None
    return max(bar.open, lim) if bar.high >= lim else None


def settle_pending(pf, orders, snap, broker):
    """Fill queued orders at the first session AFTER they were placed: MOO at that session's open,
    a limit only on a session that traded through it (walking forward, session by session). Returns
    (filled, unfilled); unfilled = a limit that has not crossed yet (a re-decide supersedes it)."""
    filled, unfilled = [], []
    for o in orders:
        hit = None
        for b in [b for b in snap.get(o["symbol"], []) if b.date > o["placed_session"]]:
            px = _fill_price(o, b)
            if px is None:
                continue
            if o["side"] == "buy":
                pf.buy(o["symbol"], broker.buy_price(px), min(o["dollars"], pf.cash), b.date, o["reason"])
            else:
                pf.sell(o["symbol"], broker.sell_price(px), b.date, o["reason"], qty=_sell_qty(o, pf))
            hit = {**o, "fill_date": b.date, "fill_price": round(px, 4)}
            break
        (filled if hit else unfilled).append(hit or o)
    return filled, unfilled


def rescale_splits(pf, snap, label=""):
    """Corporate-action guard: the RH feed restates a symbol's WHOLE price history when it splits
    (bars are split-adjusted), but a held position keeps its as-filled qty/basis — marking or
    exiting it against restated bars books phantom P&L (mirofish booked +$60 when SOXS
    reverse-split 1:10 on 2026-07-15). If a position's basis is far off its entry-date bar and the
    mismatch is a clean split ratio, rescale qty/basis in place (position value unchanged).
    # ponytail: integer ratios only, keyed off the entry-date open; warns + leaves alone otherwise.
    """
    for pos in list(pf.positions.values()):
        bars = snap.get(pos.symbol, [])
        i = next((k for k, b in enumerate(bars) if b.date == pos.entry_date), None)
        if i is None or pos.avg_price <= 0:
            continue
        r = bars[i].open / pos.avg_price
        if 0.67 < r < 1.5:               # averaging/slippage noise, not a split (splits are >=2:1)
            continue
        ratio = float(round(r)) if r > 1 else 1.0 / max(round(1.0 / r), 1)
        if ratio == 1.0 or abs(r / ratio - 1) > 0.05:
            print(f"    WARNING {label or pf.name}: {pos.symbol} basis {pos.avg_price:.4f} is "
                  f"{r:.2f}x off its {pos.entry_date} bar with no clean split ratio — left as-is")
            continue
        if i + 1 < len(bars) and not (0.5 < (bars[i + 1].open / pos.avg_price) / ratio < 2.0):
            # a real restatement rescales the whole tail; one off-scale bar is a corrupt feed bar
            # (RH re-served SOXS 2026-07-14 in pre-split scale between two post-split bars)
            print(f"    WARNING {label or pf.name}: {pos.symbol} {pos.entry_date} bar is {r:.2f}x off "
                  f"basis but the next bar isn't — corrupt bar, not a split; left as-is")
            continue
        pos.qty /= ratio
        pos.avg_price *= ratio
        print(f"    split guard {label or pf.name}: {pos.symbol} restated x{ratio:g} "
              f"-> qty {pos.qty:.6f} @ {pos.avg_price:.4f}")


def rebalance(pf, targets, prices, date, label, stop_pct=cfg.STOP_LOSS_PCT, breaker_equity=cfg.CIRCUIT_BREAKER_EQUITY):
    """Instant rebalance toward target weights at `prices` (plan -> execute -> mark). The in-hours
    fast path and the engine-parity helper the self-check below pins."""
    orders = plan_orders(pf, targets, prices, label, stop_pct, breaker_equity)
    execute_orders(pf, orders, prices, date, PaperBroker(cfg.SLIPPAGE_BPS))
    pf.mark(date, prices)


def swarm_targets(swarm):
    """Allocate across the swarm's top vote-getters, weight proportional to vote share.
    CASH votes stay in cash (un-allocated)."""
    total = swarm["total_fish"]
    cand = [(s, n) for s, n in swarm["ballots"] if s != "CASH" and n / total >= 0.05]
    cand = sorted(cand, key=lambda x: x[1], reverse=True)[:3]
    return {s: n / total for s, n in cand}


def mirofish_targets(mf, max_names=None, floor=0.05):
    """Allocate across MiroFish's rank-weighted consensus: weight ∝ each name's share of total
    Borda points, keep names clearing `floor`, up to `max_names` (cfg.MIROFISH_MAX_NAMES). The
    dropped tail + any CASH conviction stays in cash — so a low-conviction panel deploys less."""
    if max_names is None:
        max_names = cfg.MIROFISH_MAX_NAMES
    ballots = [(s, p) for s, p in mf["ballots"] if s != "CASH"]
    total = sum(p for _, p in ballots) or 1
    cand = sorted((c for c in ballots if c[1] / total >= floor), key=lambda x: x[1], reverse=True)
    return {s: p / total for s, p in cand[:max_names]}


def analyst_targets(analyst):
    return analyst.get("targets", {})


def congress_targets(cache, today, lookback_days=None, max_names=None):
    """Mirror the most-successful politicians: weight ∝ how many of the followed top filers
    DISCLOSED a buy of each name within the lookback window (consensus = conviction). Only filings
    disclosed on/before `today` count — never the earlier transaction date (that'd be look-ahead).
    Normalized over all qualifying names, so a thin/spread-out mirror leaves the tail in cash."""
    if lookback_days is None:
        lookback_days = cfg.CONGRESS_LOOKBACK_DAYS
    if max_names is None:
        max_names = cfg.CONGRESS_MAX_NAMES
    cutoff = (_dt.date.fromisoformat(today) - _dt.timedelta(days=lookback_days)).isoformat()
    counts = {}
    for t in cache.get("trades", []):
        fd = t.get("filing_date")
        if fd and cutoff <= fd <= today:
            counts.setdefault(t["ticker"], set()).add(t.get("filer_id"))
    scores = {s: len(f) for s, f in counts.items()}
    total = sum(scores.values()) or 1
    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:max_names]
    return {s: n / total for s, n in top}


if __name__ == "__main__":  # ponytail: self-check for the stop-loss / circuit-breaker branches
    # stop fires: held name down 20% (> 15%) is sold and not re-bought this tick
    pf = Portfolio(100.0, "t"); pf.buy("AAPL", 100.0, 50.0, "d0", "seed")
    rebalance(pf, {"AAPL": 0.5}, {"AAPL": 80.0}, "d1", "test")
    assert "AAPL" not in pf.positions and any("stop" in t.reason for t in pf.trades)

    # opt out: same drop with stop_pct=None keeps the position
    pf = Portfolio(100.0, "t"); pf.buy("AAPL", 100.0, 50.0, "d0", "seed")
    rebalance(pf, {"AAPL": 0.5}, {"AAPL": 80.0}, "d1", "test", stop_pct=None)
    assert "AAPL" in pf.positions

    # circuit breaker: equity below the breaker blocks new buys; breaker_equity=None re-enables
    pf = Portfolio(50.0, "t")
    rebalance(pf, {"MSFT": 0.5}, {"MSFT": 10.0}, "d1", "test")
    assert "MSFT" not in pf.positions
    pf = Portfolio(50.0, "t")
    rebalance(pf, {"MSFT": 0.5}, {"MSFT": 10.0}, "d1", "test", breaker_equity=None)
    assert "MSFT" in pf.positions

    # per-agent risk: configured override vs global fallback for an unknown name
    assert risk_for("llm_voters") == (0.15, cfg.CIRCUIT_BREAKER_EQUITY)
    assert risk_for("nope") == (cfg.STOP_LOSS_PCT, cfg.CIRCUIT_BREAKER_EQUITY)

    # mirofish_targets: weight ∝ points share, drop CASH + sub-floor tail, cap at max_names
    mf = {"ballots": [["NVDA", 6], ["MU", 2], ["AMD", 1], ["CASH", 0]]}   # total points = 9
    tg = mirofish_targets(mf, max_names=2)
    assert set(tg) == {"NVDA", "MU"} and abs(sum(tg.values()) - 8 / 9) < 1e-9  # AMD cut by the cap
    assert mirofish_targets({"ballots": [["X", 1], ["Y", 19]]}, floor=0.05) == {"X": 0.05, "Y": 0.95}  # X exactly at floor stays
    assert mirofish_targets({"ballots": [["X", 1], ["Y", 24]]}, floor=0.05) == {"Y": 0.96}             # X (4%) below floor dropped
    assert mirofish_targets({"ballots": [["CASH", 0]]}) == {}                  # all-cash panel -> no targets

    # congress_targets: weight ∝ distinct followed filers buying a name, within the disclosure window
    cache = {"trades": [
        {"ticker": "NVDA", "filer_id": "a", "filing_date": "2026-06-20"},
        {"ticker": "NVDA", "filer_id": "b", "filing_date": "2026-06-21"},  # 2 filers -> NVDA heavier
        {"ticker": "MU",   "filer_id": "a", "filing_date": "2026-06-19"},
        {"ticker": "NVDA", "filer_id": "a", "filing_date": "2026-06-20"},  # dup filer -> not double-counted
        {"ticker": "OLD",  "filer_id": "c", "filing_date": "2026-01-01"},  # outside lookback -> dropped
        {"ticker": "AHEAD", "filer_id": "d", "filing_date": "2026-12-31"},  # disclosed after `today` -> dropped
    ]}
    tg = congress_targets(cache, today="2026-06-25", lookback_days=30, max_names=5)
    assert tg == {"NVDA": 2 / 3, "MU": 1 / 3}, tg
    assert congress_targets({"trades": []}, today="2026-06-25") == {}  # empty mirror -> all cash

    # --- order lifecycle: plan -> queue -> settle at the next open ---
    from bot.models import Bar
    broker = PaperBroker(0)  # no slippage, so fills land on exact numbers

    pf = Portfolio(100.0, "t")
    orders = plan_orders(pf, {"AAPL": 0.5}, {"AAPL": 10.0}, "test")
    assert orders == [{"symbol": "AAPL", "side": "buy", "kind": "moo", "limit": None,
                       "dollars": 50.0, "qty": None, "reason": "test: buy 50%"}], orders
    for o in orders:
        o["placed_session"] = "d0"
    filled, unfilled = settle_pending(pf, orders, {"AAPL": [Bar("d1", 12.0, 13.0, 11.0, 12.5, 1)]}, broker)
    assert not unfilled and abs(pf.positions["AAPL"].qty - 50.0 / 12.0) < 1e-9        # MOO fills at the open (12)
    assert filled[0]["fill_date"] == "d1" and filled[0]["fill_price"] == 12.0

    # a queued order waits for a session strictly AFTER it was placed
    pf = Portfolio(100.0, "t")
    moo = [dict(symbol="MU", side="buy", kind="moo", limit=None, dollars=50.0, qty=None, reason="b", placed_session="d1")]
    assert settle_pending(pf, moo, {"MU": [Bar("d1", 9, 9, 9, 9, 1)]}, broker) == ([], moo)

    # a buy limit rests unless the session trades down through it
    pf = Portfolio(100.0, "t")
    lim = [dict(symbol="MU", side="buy", kind="limit", limit=8.0, dollars=50.0, qty=None, reason="b", placed_session="d0")]
    assert settle_pending(pf, lim, {"MU": [Bar("d1", 10, 10.5, 9.0, 10.0, 1)]}, broker) == ([], lim)  # low 9 > 8
    f, u = settle_pending(pf, lim, {"MU": [Bar("d1", 10, 10.5, 7.5, 8.5, 1)]}, broker)                 # low 7.5 <= 8
    assert not u and abs(pf.positions["MU"].qty - 50.0 / 8.0) < 1e-9                                   # fills at the limit (8)

    # mark dedupes by date: two marks on one date keep ONE point (no weekend/rerun churn)
    pf = Portfolio(100.0, "t"); pf.mark("d1", {}); pf.mark("d1", {})
    assert pf.equity_curve == [("d1", 100.0)], pf.equity_curve

    # split guard: 1:10 reverse split restates the entry bar x10 -> qty/10, basis x10, value unchanged
    from bot.models import Position
    pf = Portfolio(0.0, "t")
    pf.positions["SOXS"] = Position("SOXS", 1.5, 4.11, "d1")
    rescale_splits(pf, {"SOXS": [Bar("d1", 41.1, 41.8, 37.7, 40.0, 1)]})
    p = pf.positions["SOXS"]
    assert abs(p.qty - 0.15) < 1e-9 and abs(p.avg_price - 41.1) < 1e-9, (p.qty, p.avg_price)
    # 4:1 forward split -> qty x4, basis /4
    pf.positions["CRWD"] = Position("CRWD", 0.01, 735.44, "d1")
    rescale_splits(pf, {"CRWD": [Bar("d1", 183.9, 191.3, 183.0, 187.0, 1)]})
    p = pf.positions["CRWD"]
    assert abs(p.qty - 0.04) < 1e-9 and abs(p.avg_price - 183.86) < 1e-9, (p.qty, p.avg_price)
    # noise (averaged-up basis, no split) is untouched; missing entry bar is untouched
    pf.positions["MU"] = Position("MU", 1.0, 994.05, "d1")
    rescale_splits(pf, {"MU": [Bar("d1", 939.0, 999.0, 930.0, 990.0, 1)], "NOBAR": []})
    assert pf.positions["MU"].qty == 1.0 and pf.positions["MU"].avg_price == 994.05
    # one corrupt bar (entry bar 0.1x, next bar back in scale) is a bad feed bar, NOT a split
    pf.positions["GLITCH"] = Position("GLITCH", 0.35, 39.72, "d1")
    rescale_splits(pf, {"GLITCH": [Bar("d1", 3.97, 4.5, 3.97, 4.28, 1), Bar("d2", 41.2, 49.7, 41.2, 46.0, 1)]})
    p = pf.positions["GLITCH"]
    assert p.qty == 0.35 and p.avg_price == 39.72, (p.qty, p.avg_price)

    # is_rth: Wed noon ET open; Sat and pre-market closed (2026-06-24 is a Wednesday)
    assert is_rth(_dt.datetime(2026, 6, 24, 12, 0, tzinfo=_ET))
    assert not is_rth(_dt.datetime(2026, 6, 27, 12, 0, tzinfo=_ET))   # Saturday
    assert not is_rth(_dt.datetime(2026, 6, 24, 8, 0, tzinfo=_ET))    # 08:00 pre-market
    print("ok")
