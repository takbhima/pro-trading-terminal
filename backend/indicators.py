import pandas as pd
import numpy as np

# ── EMA ─────────────────────────────────────────────────────────────────────
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

# ── RSI ─────────────────────────────────────────────────────────────────────
def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=length - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

# ── ATR ─────────────────────────────────────────────────────────────────────
def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=length - 1, adjust=False).mean()

# ── Supertrend (fixed — matches Pine Script exactly) ─────────────────────────
def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               factor: float = 3.0, atr_len: int = 10) -> pd.Series:
    """
    Returns direction:  -1 = bullish (price above supertrend line)
                        +1 = bearish (price below supertrend line)

    Matches Pine Script ta.supertrend(factor, atrLen):
        direction < 0  →  bullish  →  BUY condition
        direction > 0  →  bearish  →  SELL condition
    """
    atr_vals = atr(high, low, close, atr_len)
    hl2      = (high + low) / 2.0

    # Raw bands
    raw_upper = hl2 + factor * atr_vals
    raw_lower = hl2 - factor * atr_vals

    n = len(close)
    upper  = np.zeros(n)
    lower  = np.zeros(n)
    st_dir = np.zeros(n)   # +1 bearish, -1 bullish

    close_arr  = close.values
    upper_arr  = raw_upper.values
    lower_arr  = raw_lower.values

    # Initialise first bar
    upper[0]  = upper_arr[0]
    lower[0]  = lower_arr[0]
    st_dir[0] = 1   # start bearish until proven otherwise

    for i in range(1, n):
        # ── Lower band (support in uptrend) ──────────────────────────────
        # Only tighten upward (never let support drop)
        if lower_arr[i] > lower[i-1] or close_arr[i-1] < lower[i-1]:
            lower[i] = lower_arr[i]
        else:
            lower[i] = lower[i-1]

        # ── Upper band (resistance in downtrend) ──────────────────────────
        # Only tighten downward (never let resistance rise)
        if upper_arr[i] < upper[i-1] or close_arr[i-1] > upper[i-1]:
            upper[i] = upper_arr[i]
        else:
            upper[i] = upper[i-1]

        # ── Direction ────────────────────────────────────────────────────
        if st_dir[i-1] == 1:          # previously bearish
            if close_arr[i] > upper[i]:
                st_dir[i] = -1        # flip to bullish
            else:
                st_dir[i] = 1         # stay bearish
        else:                          # previously bullish
            if close_arr[i] < lower[i]:
                st_dir[i] = 1         # flip to bearish
            else:
                st_dir[i] = -1        # stay bullish

    return pd.Series(st_dir, index=close.index, dtype=float)

# ── Cross helpers ────────────────────────────────────────────────────────────
def crossover(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) <= s2.shift(1)) & (s1 > s2)

def crossunder(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) >= s2.shift(1)) & (s1 < s2)

# ── Main ─────────────────────────────────────────────────────────────────────
def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Flatten MultiIndex columns if yfinance returns them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["fastEMA"]  = ema(df["Close"], 9)
    df["slowEMA"]  = ema(df["Close"], 21)
    df["trendEMA"] = ema(df["Close"], 200)
    df["rsi"]      = rsi(df["Close"], 14)
    df["atr"]      = atr(df["High"], df["Low"], df["Close"], 14)
    df["st_dir"]   = supertrend(df["High"], df["Low"], df["Close"], 3, 10)

    df["crossUp"]   = crossover(df["fastEMA"],  df["slowEMA"])
    df["crossDown"] = crossunder(df["fastEMA"], df["slowEMA"])

    df.dropna(inplace=True)
    return df