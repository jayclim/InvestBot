"""Performance summary for a finished portfolio."""


def summarize(pf, starting):
    eq = [v for _, v in pf.equity_curve] or [starting]
    end = eq[-1]
    peak = eq[0]
    max_dd = 0.0
    for v in eq:
        peak = max(peak, v)
        if peak > 0:
            max_dd = min(max_dd, (v - peak) / peak)
    sells = [t for t in pf.trades if t.side == "sell"]
    wins = [t for t in sells if t.pnl > 0]
    return {
        "final": end,
        "return": end / starting - 1.0,
        "max_dd": max_dd,
        "trades": len(pf.trades),
        "closed": len(sells),
        "win_rate": (len(wins) / len(sells)) if sells else 0.0,
    }
