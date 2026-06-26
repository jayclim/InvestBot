"""Virtual portfolio: cash, positions, realized trades, equity curve."""
from bot.models import Position, Trade


class Portfolio:
    def __init__(self, cash, name):
        self.name = name
        self.cash = cash
        self.positions = {}          # symbol -> Position
        self.trades = []             # list[Trade]
        self.equity_curve = []       # list[(date, equity)]
        self.halted = False

    def equity(self, prices):
        held = sum(p.qty * prices.get(p.symbol, p.avg_price) for p in self.positions.values())
        return self.cash + held

    def mark(self, date, prices):
        """Append-or-replace today's equity point (dedupe by date), so re-running a session or a
        queue-only run (book unchanged) never doubles the curve."""
        eq = round(self.equity(prices), 2)
        if self.equity_curve and self.equity_curve[-1][0] == date:
            self.equity_curve[-1] = (date, eq)
        else:
            self.equity_curve.append((date, eq))

    def buy(self, symbol, price, dollars, date, reason):
        if price <= 0 or dollars <= 0 or dollars > self.cash + 1e-9:
            return None
        qty = dollars / price
        self.cash -= qty * price
        pos = self.positions.get(symbol)
        if pos:
            total = pos.qty + qty
            pos.avg_price = (pos.avg_price * pos.qty + price * qty) / total
            pos.qty = total
        else:
            self.positions[symbol] = Position(symbol, qty, price, date)
        t = Trade(date, symbol, "buy", qty, price, qty * price, 0.0, reason)
        self.trades.append(t)
        return t

    def sell(self, symbol, price, date, reason, qty=None):
        pos = self.positions.get(symbol)
        if not pos:
            return None
        q = pos.qty if qty is None else min(qty, pos.qty)
        proceeds = q * price
        pnl = (price - pos.avg_price) * q
        self.cash += proceeds
        pos.qty -= q
        if pos.qty <= 1e-9:
            del self.positions[symbol]
        t = Trade(date, symbol, "sell", q, price, proceeds, pnl, reason)
        self.trades.append(t)
        return t
