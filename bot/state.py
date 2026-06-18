"""Persist the forward paper-test portfolios between ticks."""
import json
import os

from bot.portfolio import Portfolio
from bot.models import Position, Trade

STATE_PATH = "state/paper_state.json"


def _pf_to_dict(pf):
    return {
        "cash": pf.cash,
        "halted": pf.halted,
        "positions": [vars(p) for p in pf.positions.values()],
        "trades": [vars(t) for t in pf.trades],
        "equity_curve": pf.equity_curve,
    }


def _pf_from_dict(name, d):
    pf = Portfolio(d["cash"], name)
    pf.halted = d.get("halted", False)
    for p in d.get("positions", []):
        pf.positions[p["symbol"]] = Position(**p)
    pf.trades = [Trade(**t) for t in d.get("trades", [])]
    pf.equity_curve = [tuple(x) for x in d.get("equity_curve", [])]
    return pf


def load_state(strategy_names, starting_cash, seed_last_date):
    """Returns (last_processed_date, {name: Portfolio}).

    First run starts FLAT as of seed_last_date — no backfill — so the forward
    test is a clean out-of-sample record from 'now' onward.
    """
    if os.path.exists(STATE_PATH):
        raw = json.load(open(STATE_PATH))
        pfs = {}
        for n in strategy_names:
            if n in raw.get("portfolios", {}):
                pfs[n] = _pf_from_dict(n, raw["portfolios"][n])
            else:
                pfs[n] = Portfolio(starting_cash, n)   # newly added strategy
        return raw.get("last_date", seed_last_date), pfs
    return seed_last_date, {n: Portfolio(starting_cash, n) for n in strategy_names}


def save_state(last_date, portfolios):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    out = {
        "last_date": last_date,
        "portfolios": {n: _pf_to_dict(pf) for n, pf in portfolios.items()},
    }
    with open(STATE_PATH, "w") as f:
        json.dump(out, f, indent=0)
