"""The strategies in the bake-off. Each implements generate() and returns a Signal.
Add a new class + register it in run.py to add it to the competition."""
from bot import config as cfg
from bot.indicators import sma, rsi, avg
from bot.models import Signal


def _series(bars):
    return (
        [b.close for b in bars],
        [b.high for b in bars],
        [b.low for b in bars],
        [b.volume for b in bars],
    )


class Strategy:
    name = "base"

    def generate(self, symbol, bars, position):
        return Signal(symbol, "hold", "base")


class MomentumBreakout(Strategy):
    """Buy N-day-high breakouts confirmed by above-average volume.
    Exit when price closes back below its SMA (trend break)."""
    name = "momentum_breakout"

    def generate(self, symbol, bars, position):
        if len(bars) < cfg.BREAKOUT_LOOKBACK + 1:
            return Signal(symbol, "hold", "warmup")
        closes, highs, _lows, vols = _series(bars)
        last = bars[-1]
        prior_high = max(highs[-(cfg.BREAKOUT_LOOKBACK + 1):-1])
        avg_vol = avg(vols, cfg.VOL_LOOKBACK)
        trend = sma(closes, cfg.SMA_PERIOD)
        if position is None:
            if last.close >= prior_high and avg_vol and last.volume >= avg_vol:
                return Signal(symbol, "buy", f"breakout > {cfg.BREAKOUT_LOOKBACK}d high on volume")
            return Signal(symbol, "hold", "no breakout")
        if trend and last.close < trend:
            return Signal(symbol, "sell", "close < SMA trend break")
        return Signal(symbol, "hold", "ride")


class MeanReversion(Strategy):
    """Buy oversold (RSI < 30), sell when it swings back overbought (RSI > 70)."""
    name = "mean_reversion"

    def generate(self, symbol, bars, position):
        closes, *_ = _series(bars)
        r = rsi(closes, cfg.RSI_PERIOD)
        if r is None:
            return Signal(symbol, "hold", "warmup")
        if position is None:
            if r < cfg.RSI_OVERSOLD:
                return Signal(symbol, "buy", f"RSI {r:.0f} < {cfg.RSI_OVERSOLD} oversold")
            return Signal(symbol, "hold", f"RSI {r:.0f}")
        if r > cfg.RSI_OVERBOUGHT:
            return Signal(symbol, "sell", f"RSI {r:.0f} > {cfg.RSI_OVERBOUGHT} overbought")
        return Signal(symbol, "hold", "hold")


class Blended(Strategy):
    """Momentum breakout, but skip entries that are already overbought (RSI filter).
    Exit on trend break OR a strongly overbought reading."""
    name = "blended_momo_rsi"

    def generate(self, symbol, bars, position):
        if len(bars) < cfg.BREAKOUT_LOOKBACK + 1:
            return Signal(symbol, "hold", "warmup")
        closes, highs, _lows, vols = _series(bars)
        last = bars[-1]
        prior_high = max(highs[-(cfg.BREAKOUT_LOOKBACK + 1):-1])
        avg_vol = avg(vols, cfg.VOL_LOOKBACK)
        trend = sma(closes, cfg.SMA_PERIOD)
        r = rsi(closes, cfg.RSI_PERIOD)
        if position is None:
            if (last.close >= prior_high and avg_vol and last.volume >= avg_vol
                    and r is not None and r < cfg.RSI_OVERBOUGHT):
                return Signal(symbol, "buy", f"breakout, RSI {r:.0f} not overbought")
            return Signal(symbol, "hold", "filtered")
        if (trend and last.close < trend) or (r is not None and r > cfg.RSI_OVERBOUGHT + 5):
            return Signal(symbol, "sell", "trend break / overbought")
        return Signal(symbol, "hold", "ride")
