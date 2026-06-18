"""Walk-forward engine. Runs each strategy as its own $100 portfolio with no
lookahead: signals are computed from bars up to 'yesterday' and filled at 'today's'
open. Stops trigger intraday off the low.

`step_day` is the single source of truth for one trading day. Two callers use it:
  - run_replay() steps through a whole snapshot   -> a backtest
  - tick.py steps only the new day(s) since last  -> live forward paper test
"""
from bot import config as cfg
from bot.portfolio import Portfolio
from bot.broker import PaperBroker


def index_snapshot(snapshot):
    all_dates = sorted({b.date for bars in snapshot.values() for b in bars})
    by_sym_date = {s: {b.date: b for b in bars} for s, bars in snapshot.items()}
    return all_dates, by_sym_date


def _prices(snapshot, by_sym_date, date):
    opens, closes = {}, {}
    for s in snapshot:
        b = by_sym_date[s].get(date)
        if b:
            opens[s], closes[s] = b.open, b.close
    return opens, closes


def step_day(pf, strat, snapshot, by_sym_date, all_dates, di, broker):
    """Advance one portfolio through the single trading day all_dates[di]."""
    date = all_dates[di]
    opens, closes = _prices(snapshot, by_sym_date, date)

    # Circuit breaker: below the floor, stop opening new positions.
    if pf.equity(closes) < cfg.CIRCUIT_BREAKER_EQUITY:
        pf.halted = True

    exited = set()

    # 1) Hard stops first (triggered intraday off the low).
    for s in list(pf.positions):
        b = by_sym_date[s].get(date)
        if not b:
            continue
        stop = pf.positions[s].avg_price * (1 - cfg.STOP_LOSS_PCT)
        if b.low <= stop:
            pf.sell(s, stop, date, "stop-loss")
            exited.add(s)

    # 2) Strategy decisions from history up to yesterday, filled at today's open.
    if di >= 1:
        decision_date = all_dates[di - 1]
        for s in snapshot:
            if s in exited:
                continue
            hist = [b for b in snapshot[s] if b.date <= decision_date]
            if len(hist) < cfg.WARMUP:
                continue
            price = opens.get(s)
            if price is None:
                continue
            pos = pf.positions.get(s)
            sig = strat.generate(s, hist, pos)
            if sig.action == "sell" and pos:
                pf.sell(s, broker.sell_price(price), date, sig.reason)
                exited.add(s)
            elif sig.action == "buy" and pos is None and not pf.halted:
                if len(pf.positions) < cfg.MAX_POSITIONS:
                    target = pf.equity(closes) * cfg.POSITION_SIZE_PCT
                    dollars = min(target, pf.cash)
                    if dollars > 1.0:
                        pf.buy(s, broker.buy_price(price), dollars, date, sig.reason)

    pf.equity_curve.append((date, pf.equity(closes)))


def run_replay(snapshot, strategy_factories):
    broker = PaperBroker(cfg.SLIPPAGE_BPS)
    all_dates, by_sym_date = index_snapshot(snapshot)
    results = {}
    for make in strategy_factories:
        strat = make()
        pf = Portfolio(cfg.STARTING_CASH, strat.name)
        for di in range(len(all_dates)):
            step_day(pf, strat, snapshot, by_sym_date, all_dates, di, broker)
        results[strat.name] = pf
    return results
