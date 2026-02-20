import pandas as pd

RR = 2.0  # Risk:Reward ratio

def generate_signal(df_5m: pd.DataFrame, df_15m: pd.DataFrame = None) -> dict | None:
    """
    Check the last fully closed candle for BUY / SELL signal.
    Uses df_5m as primary timeframe. df_15m reserved for future MTF confluence.
    Returns signal dict or None.
    """
    if df_5m is None or len(df_5m) < 5:
        return None

    # Use second-to-last bar (last closed candle, not live bar)
    bar = df_5m.iloc[-2]

    close = float(bar["Close"])
    atr   = float(bar["atr"])

    if bar.get("longCond", False) or (
        bar["crossUp"] and bar["rsi"] > 50
        and close > bar["trendEMA"]
        and bar["st_dir"] < 0
    ):
        return {
            "type" : "BUY",
            "price": round(close, 2),
            "sl"   : round(close - atr,       2),
            "tp"   : round(close + atr * RR,  2),
            "atr"  : round(atr, 2),
            "rsi"  : round(float(bar["rsi"]), 2),
        }

    if bar.get("shortCond", False) or (
        bar["crossDown"] and bar["rsi"] < 50
        and close < bar["trendEMA"]
        and bar["st_dir"] > 0
    ):
        return {
            "type" : "SELL",
            "price": round(close, 2),
            "sl"   : round(close + atr,       2),
            "tp"   : round(close - atr * RR,  2),
            "atr"  : round(atr, 2),
            "rsi"  : round(float(bar["rsi"]), 2),
        }

    return None
