"""Run one paper-trading tick for the agents — and let you shape the tick.

    python3 run_agents.py                          # default: swarm, mirofish, analyst, rules, dashboard
    python3 run_agents.py --only swarm             # just one step
    python3 run_agents.py --skip mirofish          # everything except a step
    python3 run_agents.py --steps swarm,swarm,dashboard   # explicit order; repeats allowed
    python3 run_agents.py --mirofish-tier qwen     # pick the real-MiroFish cost/fidelity tier
    python3 run_agents.py --estimate               # print projected swarm + mirofish cost, run nothing

Steps:
  swarm      — independent-voter swarm (bot/swarm.py) -> rebalance llm_voters book
  mirofish   — real-MiroFish social-sim swarm (bot/mirofish.py, tiered) -> rebalance mirofish_real book
  analyst    — read state/analyst.json (written by the financial-analyst skill) -> rebalance analyst book
  congress   — mirror the most successful members of Congress (tools/refresh_congress.py) -> rebalance congress book
  rules      — advance the rule strategies' forward test (tick.py)
  dashboard  — publish web/public/state.json + history.json (tools/build_dashboard.py)

Paper only. No real Robinhood orders are placed here. Network steps (swarm, mirofish) cost real
money on OpenRouter; everything else is local. The analyst REPORT is produced separately by the
financial-analyst skill — this runner only rebalances toward the targets it already wrote.
"""
import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import config as cfg
from bot import paper
from bot.broker import PaperBroker
from bot.mirofish import TIERS as MIROFISH_TIERS
from run import load_snapshot

ROOT = os.path.dirname(os.path.abspath(__file__))


def latest_prices(snap):
    return {s: bars[-1].close for s, bars in snap.items() if bars}


def _order_desc(o):
    amt = f"${o['dollars']:.2f}" if o.get("dollars") else f"{(o.get('qty') or 0):.3f}sh"
    kind = f"@{o['limit']} lim" if o.get("kind") == "limit" and o.get("limit") is not None else "MOO"
    return f"{o['side']} {o['symbol']} {amt} {kind}"


def _read_seed():
    """Optional world-events seed for MiroFish — recent headlines/signals. Populate
    state/news_seed.txt (the run-agents skill can write it); absent = price-action only."""
    p = os.path.join(ROOT, "state", "news_seed.txt")
    return open(p).read() if os.path.exists(p) else None


def _decide(name, targets, ctx, label, limits=None):
    """Settle this agent's queued orders at any newly-available open, then plan the move toward
    `targets` and either fill it instantly (in RTH) or queue it for the next open. A re-decide
    supersedes any still-resting orders — that's how 'cancel/adjust as news comes' falls out."""
    _, pfs, pending = paper.load_agents(cfg.AGENT_NAMES)
    pf, broker = pfs[name], PaperBroker(cfg.SLIPPAGE_BPS)
    stop, breaker = paper.risk_for(name)
    paper.rescale_splits(pf, ctx["snap"], label)  # split guard BEFORE any fill/mark on restated bars
    filled, _resting = paper.settle_pending(pf, pending.get(name, []), ctx["snap"], broker)
    orders = paper.plan_orders(pf, targets, ctx["prices"], label, stop, breaker, limits)
    if ctx["instant"]:
        paper.execute_orders(pf, orders, ctx["prices"], ctx["today"], broker)
        pending[name] = []
        verb = f"filled {len(orders)} order(s) instantly (RTH)"
    else:
        for o in orders:
            o["placed_session"] = ctx["today"]
        pending[name] = orders
        verb = f"queued {len(orders)} order(s) for next open"
    pf.mark(ctx["today"], ctx["prices"])
    paper.save_agents(ctx["today"], pfs, pending)
    settled = f", settled {len(filled)} from a prior open" if filled else ""
    print(f"    {label}: {verb}{settled}")


def _refresh_news():
    """Pull fresh headlines BEFORE any agent/algo runs (date-cached: one throttled sweep per
    calendar day, instant reuse after). Enriches the swarm briefing and the site."""
    from bot.swarm import refresh_news
    n = refresh_news(cfg.UNIVERSE, os.path.join(ROOT, "state", "news.json"))
    items = n.get("items", {})
    print(f"news: {sum(len(v) for v in items.values())} headlines across {len(items)} names (cached {n.get('date')})")


def step_swarm(ctx):
    from bot.swarm import run_swarm, load_news
    news_path = os.path.join(ROOT, "state", "news.json")
    print("swarm: ~150 OpenRouter calls (~$0.07-0.20)…")
    sw = run_swarm(ctx["snap"], cfg.UNIVERSE, load_news(news_path))
    json.dump(sw, open(os.path.join(ROOT, "state", "swarm.json"), "w"))
    print(f"  swarm: {sw['call']} ({int(sw['confidence']*100)}%), {sw['total_fish']} fish")
    _decide("llm_voters", paper.swarm_targets(sw), ctx, "swarm")


def step_mirofish(ctx):
    from bot.mirofish import estimate, run_mirofish
    tier = ctx["mirofish_tier"]
    e = estimate(tier)
    print(f"mirofish: tier '{tier}', ~{e['calls']} OpenRouter calls (est ${e['cost_low']}-{e['cost_high']})…")
    mf = run_mirofish(ctx["snap"], cfg.UNIVERSE, tier, _read_seed())
    json.dump(mf, open(os.path.join(ROOT, "state", "mirofish.json"), "w"))
    conv = " -> ".join(f"{c['top']}({int(c['share']*100)}%)" for c in mf["convergence"])
    print(f"  mirofish: {mf['call']} ({int(mf['confidence']*100)}%) after {mf['rounds']} rounds | {conv}")
    _decide("mirofish_real", paper.mirofish_targets(mf), ctx, "mirofish")


def step_analyst(ctx):
    ap = os.path.join(ROOT, "state", "analyst.json")
    if not os.path.exists(ap):
        print("analyst: no state/analyst.json yet — run the financial-analyst skill first; skipping.")
        return
    analyst = json.load(open(ap))
    print(f"  analyst: targets {analyst.get('targets', {})}")
    _decide("deep_research_analyst", paper.analyst_targets(analyst), ctx, "analyst", analyst.get("limits"))


def step_congress(ctx):
    from tools.refresh_congress import refresh_congress
    c = refresh_congress(today=ctx["today"])
    if c.get("error"):
        print(f"  congress: feed unavailable, no cache ({c['error']}) — book left as-is")
    tg = paper.congress_targets(c, ctx["today"])
    shown = ", ".join(f"{s}({int(w*100)}%)" for s, w in sorted(tg.items(), key=lambda kv: -kv[1])) or "flat"
    print(f"  congress: {len(c.get('leaders', []))} active members / {c.get('followed', 0)} filers -> {shown}")
    _decide("congress_mirror", tg, ctx, "congress")


def step_rules(ctx):
    import tick
    tick.main()


def step_dashboard(ctx):
    from tools import build_dashboard
    build_dashboard.main()


STEPS = {"swarm": step_swarm, "mirofish": step_mirofish, "analyst": step_analyst,
         "congress": step_congress, "rules": step_rules, "dashboard": step_dashboard}
DEFAULT_STEPS = ["swarm", "mirofish", "analyst", "congress", "rules", "dashboard"]
NETWORK_STEPS = {"swarm", "mirofish", "congress"}  # external (cost money or a live feed); skip (don't abort) on failure


def resolve_steps(args):
    if args.steps:
        steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    elif args.only:
        steps = [args.only]
    elif args.skip:
        skip = {s.strip() for s in args.skip.split(",")}
        steps = [s for s in DEFAULT_STEPS if s not in skip]
    else:
        steps = list(DEFAULT_STEPS)
    bad = [s for s in steps if s not in STEPS]
    if bad:
        sys.exit(f"unknown step(s) {bad}; valid: {list(STEPS)}")
    return steps


def main():
    ap = argparse.ArgumentParser(description="Run/shape one agents paper-trading tick.")
    ap.add_argument("--steps", help="explicit comma-separated step order; repeats allowed")
    ap.add_argument("--only", help="run a single step")
    ap.add_argument("--skip", help="comma-separated steps to drop from the default tick")
    ap.add_argument("--mirofish-tier", default="cheap", choices=list(MIROFISH_TIERS), dest="mirofish_tier",
                    help="real-MiroFish cost/fidelity tier (default: cheap)")
    ap.add_argument("--estimate", action="store_true", help="print projected network cost and exit")
    ap.add_argument("--fill-mode", default="auto", choices=["auto", "instant", "queue"], dest="fill_mode",
                    help="auto (default): fill instantly during market hours, else queue orders for the "
                         "next session's open; instant/queue force one path regardless of the clock")
    args = ap.parse_args()

    if args.estimate:
        from bot.mirofish import estimate
        e = estimate(args.mirofish_tier)
        print(f"swarm   : ~150 calls, est $0.07-0.20")
        print(f"mirofish: tier '{e['tier']}', {e['agents']} agents x {e['rounds']} rounds = "
              f"~{e['calls']} calls, est ${e['cost_low']}-{e['cost_high']} (mid ${e['cost_mid']})")
        print("(estimates only; local steps — analyst/rules/dashboard — are free)")
        return

    steps = resolve_steps(args)
    snap = load_snapshot(os.path.join(ROOT, "data", "snapshot.json"))
    today = sorted({b.date for bars in snap.values() for b in bars})[-1]
    rth = paper.is_rth()
    instant = {"auto": rth, "instant": True, "queue": False}[args.fill_mode]
    ctx = {"snap": snap, "today": today, "prices": latest_prices(snap),
           "mirofish_tier": args.mirofish_tier, "rth": rth, "instant": instant}

    print(f"tick @ {today} — steps: {', '.join(steps)}")
    flow = "fill instantly" if instant else "queue for the next open"
    print(f"clock: {'RTH' if rth else 'outside RTH'} (ET) · fill-mode={args.fill_mode} → orders {flow}")
    age = (_dt.date.today() - _dt.date.fromisoformat(today)).days
    if age > 4:  # ponytail: 4d covers a Fri→Mon + holiday; wider gap = the MCP refresh got skipped
        print(f"⚠ snapshot last bar {today} is {age}d old — refresh market data (Robinhood MCP) before a real tick.")
    if any(s != "dashboard" for s in steps):  # fresh news before any agent/algo (not a publish-only run)
        _refresh_news()
    for s in steps:
        try:
            STEPS[s](ctx)
        except Exception as e:
            if s in NETWORK_STEPS:
                print(f"  {s} skipped — {e}")
            else:
                raise

    print(f"\nAgent paper books @ {today}:")
    _, pfs, pending = paper.load_agents(cfg.AGENT_NAMES)
    for n in cfg.AGENT_NAMES:
        pf = pfs[n]
        held = ", ".join(f"{s} {p.qty:.3f}@{p.avg_price:.2f}" for s, p in pf.positions.items()) or "flat"
        print(f"  {n:22s} equity ${pf.equity(ctx['prices']):7.2f} · cash ${pf.cash:6.2f} · {held}")
        q = pending.get(n) or []
        if q:
            print(f"  {'':22s}   ↳ {len(q)} open order(s) for next open: {', '.join(_order_desc(o) for o in q)}")


if __name__ == "__main__":
    main()
