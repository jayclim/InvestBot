"""Run one paper-trading round for the AI agents (analyst + swarm), on fake money.

    python run_agents.py

- Runs the mirofish swarm live (OpenRouter) and saves the result to state/swarm.json.
- Reads the analyst report from state/analyst.json.
- Rebalances each agent's $100 paper book toward its targets at the latest prices —
  buying/selling multiple names as needed — and appends to its equity track record
  in state/agent_state.json.

Paper only. No real Robinhood orders are placed here.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import config as cfg
from bot import paper
from run import load_snapshot

ROOT = os.path.dirname(os.path.abspath(__file__))


def latest_prices(snap):
    return {s: bars[-1].close for s, bars in snap.items() if bars}


def main():
    snap = load_snapshot(os.path.join(ROOT, "data", "snapshot.json"))
    today = sorted({b.date for bars in snap.values() for b in bars})[-1]
    prices = latest_prices(snap)

    # 1) Swarm — live election via OpenRouter
    swarm = None
    try:
        from bot.swarm import run_swarm
        print("running swarm (≈150 OpenRouter calls, ~$0.20)…")
        swarm = run_swarm(snap, cfg.UNIVERSE)
        json.dump(swarm, open(os.path.join(ROOT, "state", "swarm.json"), "w"))
        print(f"  swarm: {swarm['call']} ({int(swarm['confidence']*100)}%), {swarm['total_fish']} fish")
    except Exception as e:
        print(f"  swarm skipped — {e}")

    # 2) Analyst — read the report produced by the agent-driven research step
    ap = os.path.join(ROOT, "state", "analyst.json")
    analyst = json.load(open(ap)) if os.path.exists(ap) else None

    # 3) Rebalance each agent's fake-money book
    _, pfs = paper.load_agents(cfg.AGENT_NAMES)
    if analyst:
        paper.rebalance(pfs["deep_research_analyst"], paper.analyst_targets(analyst), prices, today, "analyst")
    if swarm:
        paper.rebalance(pfs["mirofish_swarm"], paper.swarm_targets(swarm), prices, today, "swarm")
    paper.save_agents(today, pfs)

    print(f"\nAgent paper books @ {today}:")
    for n in cfg.AGENT_NAMES:
        pf = pfs[n]
        held = ", ".join(f"{s} {p.qty:.3f}@{p.avg_price:.2f}" for s, p in pf.positions.items()) or "flat"
        print(f"  {n:22s} equity ${pf.equity(prices):7.2f} · cash ${pf.cash:6.2f} · {held}")


if __name__ == "__main__":
    main()
