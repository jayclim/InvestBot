"""Pure-Python indicators (no numpy/pandas needed)."""


def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def avg(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rolling_high(highs, period):
    if len(highs) < period:
        return None
    return max(highs[-period:])


def rsi(closes, period=14):
    """Wilder's RSI."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
