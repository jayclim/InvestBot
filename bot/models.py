"""Plain data containers shared across the harness."""
from dataclasses import dataclass


@dataclass
class Bar:
    date: str          # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    symbol: str
    action: str        # "buy" | "sell" | "hold"
    reason: str
    strength: float = 1.0


@dataclass
class Position:
    symbol: str
    qty: float         # fractional shares allowed (Robinhood supports them)
    avg_price: float
    entry_date: str


@dataclass
class Trade:
    date: str
    symbol: str
    side: str          # "buy" | "sell"
    qty: float
    price: float
    value: float
    pnl: float = 0.0   # realized, on sells
    reason: str = ""
