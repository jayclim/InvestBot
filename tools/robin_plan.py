"""Run the FUNDED rule strategies FRESH against the real Robinhood Agentic account's CURRENT
positions, per state/robin_alloc.json — the orders momentum (etc.) would place now, NOT a copy
of the paper simulation. Only algos with weight > 0 run.

    python3 tools/robin_plan.py <real_equity> [--positions '<json>']   # prints the order plan
    python3 tools/robin_plan.py --selfcheck

<json> = the live Agentic holdings as [{"symbol":..,"qty":..,"avg_price":..}] (default: flat).
Each funded strategy sees the real positions, decides buy/sell/hold on the latest completed bar,
and sizes new entries like the engine: POSITION_SIZE_PCT of its allocated capital, capped at
MAX_POSITIONS, by available cash. No orders are placed here — the run-robin skill reviews +
confirms each before placing via the MCP.

Only rule strategies are funded today. A funded AGENT (analyst/swarm/…) would instead mirror its
latest target weights (rerunning it costs money); add that path when an agent is actually funded.
ponytail: positions are treated as one shared pool — fine at one funded strategy; multi-strategy
attribution on a single account needs per-algo tagging, add it only if you fund more than one.
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import config as cfg
from bot.strategy import MomentumBreakout, MeanReversion, Blended
from run import load_snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = {c.name: c for c in (MomentumBreakout, MeanReversion, Blended)}


def _funded():
    raw = json.load(open(os.path.join(ROOT, "state", "robin_alloc.json")))
    return {a: w for a, w in raw.get("alloc", {}).items() if w and w > 0}


def fresh_orders(real_equity, positions, snap=None, funded=None):
    """Return (orders, cash_left, unfunded_agents). orders: buys carry `dollars`, sells `qty`."""
    funded = funded if funded is not None else _funded()
    snap = snap if snap is not None else load_snapshot(os.path.join(ROOT, "data", "snapshot.json"))
    marks = {s: bars[-1].close for s, bars in snap.items() if bars}
    held = {h["symbol"]: h for h in positions}
    unfunded_agents = [a for a in funded if a not in RULES]
    orders, cash_left = [], real_equity
    for algo, w in funded.items():
        if algo not in RULES:
            continue  # agents handled elsewhere (target-weight mirror) — none funded today
        strat = RULES[algo]()
        allocated = w * real_equity
        breaker = cfg.CIRCUIT_BREAKER_EQUITY * (allocated / cfg.STARTING_CASH)  # scale floor to the sub-book
        halted = allocated < breaker
        held_val = sum(h["qty"] * marks.get(s, h.get("avg_price", 0)) for s, h in held.items())
        cash_left = max(0.0, allocated - held_val)
        n = len(held)
        # 1) Sells — held names this strategy now wants out of (trend break / overbought).
        for s, h in list(held.items()):
            hist = snap.get(s, [])
            if not hist:
                continue
            pos = types.SimpleNamespace(avg_price=h.get("avg_price", 0), qty=h["qty"])
            if strat.generate(s, hist, pos).action == "sell":
                orders.append({"symbol": s, "side": "sell", "qty": round(h["qty"], 6),
                               "reason": strat.generate(s, hist, pos).reason})
                cash_left += h["qty"] * marks.get(s, h.get("avg_price", 0))
                n -= 1
        # 2) Buys — unheld names breaking out as of the latest bar, sized like the engine.
        for s in sorted(snap):
            if s in held or s in cfg.BENCHMARKS:
                continue
            hist = snap.get(s, [])
            if len(hist) < cfg.WARMUP:
                continue
            sig = strat.generate(s, hist, None)
            if sig.action == "buy" and n < cfg.MAX_POSITIONS and not halted:
                target = allocated * cfg.POSITION_SIZE_PCT
                dollars = round(min(target, cash_left), 2)
                if dollars > 1.0:
                    orders.append({"symbol": s, "side": "buy", "dollars": dollars, "reason": sig.reason})
                    cash_left -= dollars
                    n += 1
    return orders, round(cash_left, 2), unfunded_agents


def main(real_equity, positions):
    orders, cash_left, unfunded = fresh_orders(real_equity, positions)
    funded = _funded()
    print(f"Funded: {', '.join(f'{a} {int(w*100)}%' for a, w in funded.items()) or '(none)'}")
    print(f"Real equity: ${real_equity:,.2f} · current positions: {len(positions)}\n")
    if unfunded:
        print(f"NOTE: funded agents {unfunded} use target-weight mirroring — not handled here (fund rule strategies).\n")
    if not orders:
        print("No orders — nothing is breaking out / no exits. Stay as-is.")
        return
    print(f"{'side':5} {'symbol':8} {'size':>10}  reason")
    print("-" * 60)
    for o in orders:
        size = f"${o['dollars']:.2f}" if o["side"] == "buy" else f"{o['qty']:.4f} sh"
        print(f"{o['side']:5} {o['symbol']:8} {size:>10}  {o['reason']}")
    print(f"\nleftover cash ≈ ${cash_left:.2f}. Review + confirm each before placing (run-robin skill).")
    print("Dollar/fractional orders only fill in REGULAR HOURS — place during the session, not after close.")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        mk = lambda c, h, v: types.SimpleNamespace(close=c, high=h, low=min(c, h), volume=v, open=c, date="d")
        flat = [mk(100, 100, 1000) for _ in range(30)]
        snap = {"AAA": flat + [mk(115, 115, 3000)],   # fresh 20-day-high breakout on 3x volume → buy
                "BBB": flat + [mk(95, 95, 1000)]}      # below the 20-day high → no order
        orders, cash, _ = fresh_orders(100.0, [], snap=snap, funded={"momentum_breakout": 1.0})
        syms = {o["symbol"]: o for o in orders}
        assert "AAA" in syms and syms["AAA"]["side"] == "buy", orders
        assert "BBB" not in syms, orders
        assert abs(syms["AAA"]["dollars"] - 20.0) < 1e-6, orders  # 20% of $100
        print("robin_plan ok", orders, "cash", cash)
    else:
        argv = sys.argv[1:]
        pos = []
        if "--positions" in argv:
            i = argv.index("--positions")
            pos = json.loads(argv[i + 1])
            argv = argv[:i] + argv[i + 2:]
        main(float(argv[0]) if argv else 100.0, pos)
