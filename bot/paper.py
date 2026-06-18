"""Paper accounts for the AI agents (analyst + swarm).

Each agent gets its own $100 book. On every run it can buy multiple names and sell
multiple names — we rebalance the book toward a set of target weights at current
prices, with slippage. State persists in state/agent_state.json so the forward
track record accrues across runs. No real money touches this.
"""
import json
import os

from bot import config as cfg
from bot.portfolio import Portfolio
from bot.broker import PaperBroker
from bot.state import _pf_to_dict, _pf_from_dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "agent_state.json")


def load_agents(names):
    if os.path.exists(PATH):
        raw = json.load(open(PATH))
        pfs = {}
        for n in names:
            pfs[n] = (_pf_from_dict(n, raw["portfolios"][n])
                      if n in raw.get("portfolios", {}) else Portfolio(cfg.STARTING_CASH, n))
        return raw.get("last_date"), pfs
    return None, {n: Portfolio(cfg.STARTING_CASH, n) for n in names}


def save_agents(date, pfs):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump({"last_date": date, "portfolios": {n: _pf_to_dict(pf) for n, pf in pfs.items()}},
              open(PATH, "w"), indent=0)


def rebalance(pf, targets, prices, date, label):
    """Move the book toward target weights {symbol: fraction-of-equity}. Sells anything
    not targeted, then buys/trims toward each target. Supports many buys + many sells."""
    broker = PaperBroker(cfg.SLIPPAGE_BPS)
    targets = {s: min(w, cfg.AGENT_MAX_WEIGHT) for s, w in targets.items() if w > 0 and s in prices}

    # 1) exit anything no longer targeted
    for s in list(pf.positions):
        if s not in targets:
            px = prices.get(s, pf.positions[s].avg_price)
            pf.sell(s, broker.sell_price(px), date, f"{label}: exit")

    # 2) buy / trim toward each target weight
    equity = pf.equity(prices)
    for s, w in sorted(targets.items(), key=lambda kv: kv[1]):  # trims first, then buys
        target_dollars = equity * w
        cur = pf.positions.get(s)
        cur_dollars = cur.qty * prices[s] if cur else 0.0
        diff = target_dollars - cur_dollars
        if diff > 1.0 and pf.cash > 1.0:
            pf.buy(s, broker.buy_price(prices[s]), min(diff, pf.cash), date, f"{label}: buy {w*100:.0f}%")
        elif diff < -1.0 and cur:
            qty = min(cur.qty, (-diff) / prices[s])
            pf.sell(s, broker.sell_price(prices[s]), date, f"{label}: trim", qty=qty)

    pf.equity_curve.append((date, round(pf.equity(prices), 2)))


def swarm_targets(swarm):
    """Allocate across the swarm's top vote-getters, weight proportional to vote share.
    CASH votes stay in cash (un-allocated)."""
    total = swarm["total_fish"]
    cand = [(s, n) for s, n in swarm["ballots"] if s != "CASH" and n / total >= 0.05]
    cand = sorted(cand, key=lambda x: x[1], reverse=True)[:3]
    return {s: n / total for s, n in cand}


def analyst_targets(analyst):
    return analyst.get("targets", {})
