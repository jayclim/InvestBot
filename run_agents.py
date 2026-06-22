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
  rules      — advance the rule strategies' forward test (tick.py)
  dashboard  — publish web/public/state.json + history.json (tools/build_dashboard.py)

Paper only. No real Robinhood orders are placed here. Network steps (swarm, mirofish) cost real
money on OpenRouter; everything else is local. The analyst REPORT is produced separately by the
financial-analyst skill — this runner only rebalances toward the targets it already wrote.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import config as cfg
from bot import paper
from bot.mirofish import TIERS as MIROFISH_TIERS
from run import load_snapshot

ROOT = os.path.dirname(os.path.abspath(__file__))


def latest_prices(snap):
    return {s: bars[-1].close for s, bars in snap.items() if bars}


def _read_seed():
    """Optional world-events seed for MiroFish — recent headlines/signals. Populate
    state/news_seed.txt (the run-agents skill can write it); absent = price-action only."""
    p = os.path.join(ROOT, "state", "news_seed.txt")
    return open(p).read() if os.path.exists(p) else None


def _rebalance(name, targets, ctx, label):
    _, pfs = paper.load_agents(cfg.AGENT_NAMES)
    paper.rebalance(pfs[name], targets, ctx["prices"], ctx["today"], label, *paper.risk_for(name))
    paper.save_agents(ctx["today"], pfs)


def step_swarm(ctx):
    from bot.swarm import run_swarm
    print("swarm: ~150 OpenRouter calls (~$0.07-0.20)…")
    sw = run_swarm(ctx["snap"], cfg.UNIVERSE)
    json.dump(sw, open(os.path.join(ROOT, "state", "swarm.json"), "w"))
    print(f"  swarm: {sw['call']} ({int(sw['confidence']*100)}%), {sw['total_fish']} fish")
    _rebalance("llm_voters", paper.swarm_targets(sw), ctx, "swarm")


def step_mirofish(ctx):
    from bot.mirofish import estimate, run_mirofish
    tier = ctx["mirofish_tier"]
    e = estimate(tier)
    print(f"mirofish: tier '{tier}', ~{e['calls']} OpenRouter calls (est ${e['cost_low']}-{e['cost_high']})…")
    mf = run_mirofish(ctx["snap"], cfg.UNIVERSE, tier, _read_seed())
    json.dump(mf, open(os.path.join(ROOT, "state", "mirofish.json"), "w"))
    conv = " -> ".join(f"{c['top']}({int(c['share']*100)}%)" for c in mf["convergence"])
    print(f"  mirofish: {mf['call']} ({int(mf['confidence']*100)}%) after {mf['rounds']} rounds | {conv}")
    _rebalance("mirofish_real", paper.swarm_targets(mf), ctx, "mirofish")


def step_analyst(ctx):
    ap = os.path.join(ROOT, "state", "analyst.json")
    if not os.path.exists(ap):
        print("analyst: no state/analyst.json yet — run the financial-analyst skill first; skipping.")
        return
    analyst = json.load(open(ap))
    _rebalance("deep_research_analyst", paper.analyst_targets(analyst), ctx, "analyst")
    print(f"  analyst: rebalanced toward {analyst.get('targets', {})}")


def step_rules(ctx):
    import tick
    tick.main()


def step_dashboard(ctx):
    from tools import build_dashboard
    build_dashboard.main()


STEPS = {"swarm": step_swarm, "mirofish": step_mirofish, "analyst": step_analyst,
         "rules": step_rules, "dashboard": step_dashboard}
DEFAULT_STEPS = ["swarm", "mirofish", "analyst", "rules", "dashboard"]
NETWORK_STEPS = {"swarm", "mirofish"}   # cost money; skip (don't abort) if they fail


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
    ctx = {"snap": snap, "today": today, "prices": latest_prices(snap), "mirofish_tier": args.mirofish_tier}

    print(f"tick @ {today} — steps: {', '.join(steps)}")
    for s in steps:
        try:
            STEPS[s](ctx)
        except Exception as e:
            if s in NETWORK_STEPS:
                print(f"  {s} skipped — {e}")
            else:
                raise

    print(f"\nAgent paper books @ {today}:")
    _, pfs = paper.load_agents(cfg.AGENT_NAMES)
    for n in cfg.AGENT_NAMES:
        pf = pfs[n]
        held = ", ".join(f"{s} {p.qty:.3f}@{p.avg_price:.2f}" for s, p in pf.positions.items()) or "flat"
        print(f"  {n:22s} equity ${pf.equity(ctx['prices']):7.2f} · cash ${pf.cash:6.2f} · {held}")


if __name__ == "__main__":
    main()
