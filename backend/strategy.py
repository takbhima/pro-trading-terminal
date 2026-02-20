def generate_signal(df_5m, df_15m):
    last_5 = df_5m.iloc[-1]
    last_15 = df_15m.iloc[-1]

    trend_bullish = last_15["ema20"] > last_15["ema50"]
    trend_bearish = last_15["ema20"] < last_15["ema50"]

    if last_5["ema20"] > last_5["ema50"] and last_5["rsi"] > 55 and trend_bullish:
        return "BUY"

    if last_5["ema20"] < last_5["ema50"] and last_5["rsi"] < 45 and trend_bearish:
        return "SELL"

    return None
