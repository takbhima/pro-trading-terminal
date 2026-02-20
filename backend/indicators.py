import ta

def apply_indicators(df):
    df["ema20"] = ta.trend.ema_indicator(df["Close"], window=20)
    df["ema50"] = ta.trend.ema_indicator(df["Close"], window=50)
    df["rsi"] = ta.momentum.rsi(df["Close"], window=14)
    return df
