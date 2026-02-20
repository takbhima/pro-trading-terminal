import pandas as pd
import numpy as np

# ── EMA ─────────────────────────────────────────────────────────────────────
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

# ── RSI ─────────────────────────────────────────────────────────────────────
def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
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

# ── Supertrend ───────────────────────────────────────────────────────────────
def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               factor: float = 3.0, atr_len: int = 10):
    """
    Returns direction series:  -1 = bullish (price above ST)
                                +1 = bearish (price below ST)
    Matches Pine Script: direction < 0 → bullish, direction > 0 → bearish
    """
    atr_vals = atr(high, low, close, atr_len)
    hl2      = (high + low) / 2

    upper_band = hl2 + factor * atr_vals
    lower_band = hl2 - factor * atr_vals

    direction = pd.Series(index=close.index, dtype=float)
    st        = pd.Series(index=close.index, dtype=float)

    for i in range(1, len(close)):
        # Lower band
        lb = lower_band.iloc[i]
        if lower_band.iloc[i - 1] > lb:
            lb = lower_band.iloc[i - 1]
        # But reset if price was below previous lower band
        if close.iloc[i - 1] < (st.iloc[i - 1] if not np.isnan(st.iloc[i - 1]) else lb):
            lb = lower_band.iloc[i]

        # Upper band
        ub = upper_band.iloc[i]
        if upper_band.iloc[i - 1] < ub:
            ub = upper_band.iloc[i - 1]
        if close.iloc[i - 1] > (st.iloc[i - 1] if not np.isnan(st.iloc[i - 1]) else ub):
            ub = upper_band.iloc[i]

        # Direction
        prev_dir = direction.iloc[i - 1] if not np.isnan(direction.iloc[i - 1]) else 1
        if prev_dir == 1:          # was bearish
            if close.iloc[i] > ub:
                direction.iloc[i] = -1
                st.iloc[i] = lb
            else:
                direction.iloc[i] = 1
                st.iloc[i] = ub
        else:                      # was bullish
            if close.iloc[i] < lb:
                direction.iloc[i] = 1
                st.iloc[i] = ub
            else:
                direction.iloc[i] = -1
                st.iloc[i] = lb

    return direction

# ── Cross helpers ────────────────────────────────────────────────────────────
def crossover(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) <= s2.shift(1)) & (s1 > s2)

def crossunder(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) >= s2.shift(1)) & (s1 < s2)

# ── Main apply function ──────────────────────────────────────────────────────
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
