import pandas as pd
import pandas_ta as ta

# ── Supertrend helper ───────────────────────────────────────────────────────
def _supertrend_direction(df: pd.DataFrame, factor: int = 3, atr_len: int = 10) -> pd.Series:
    st = ta.supertrend(df["High"], df["Low"], df["Close"],
                       length=atr_len, multiplier=float(factor))
    dir_col = [c for c in st.columns if c.startswith("SUPERTd")][0]
    return st[dir_col]

# ── Cross helpers ───────────────────────────────────────────────────────────
def crossover(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) <= s2.shift(1)) & (s1 > s2)

def crossunder(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) >= s2.shift(1)) & (s1 < s2)

# ── Main indicator function ─────────────────────────────────────────────────
def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # EMAs
    df["fastEMA"]  = ta.ema(df["Close"], length=9)
    df["slowEMA"]  = ta.ema(df["Close"], length=21)
    df["trendEMA"] = ta.ema(df["Close"], length=200)

    # RSI & ATR
    df["rsi"] = ta.rsi(df["Close"], length=14)
    df["atr"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

    # Supertrend direction: -1 = bullish, +1 = bearish  (matches Pine)
    df["st_dir"] = _supertrend_direction(df)

    # Cross signals
    df["crossUp"]   = crossover(df["fastEMA"],  df["slowEMA"])
    df["crossDown"] = crossunder(df["fastEMA"], df["slowEMA"])

    df.dropna(inplace=True)
    return df
