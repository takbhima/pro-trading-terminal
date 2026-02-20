import pandas as pd
import time

# How much data we need per interval to compute EMA 200 reliably
# EMA 200 needs at least 300 bars to be accurate
PERIOD_MAP = {
    "1m" : "7d",
    "2m" : "7d",
    "5m" : "60d",
    "15m": "60d",   # 60d × ~26 bars/day = ~1560 bars ✓
    "30m": "60d",
    "60m": "730d",  # 2 years of hourly
    "1h" : "730d",
    "1d" : "2y",
    "1wk": "10y",
    "1mo": "10y",
}

def get_data(symbol: str, interval: str = "1d", period: str = None) -> pd.DataFrame:
    if period is None:
        period = PERIOD_MAP.get(interval, "2y")

    df = _try_ticker(symbol, interval, period)
    if df is not None and len(df) > 50:
        return df

    df = _try_download(symbol, interval, period)
    if df is not None and len(df) > 50:
        return df

    raise ValueError(f"No data returned for {symbol} after 3 attempts")


def _try_ticker(symbol, interval, period):
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        return _clean(df, symbol, "Ticker")
    except Exception as e:
        print(f"[WARN] Ticker failed {symbol}: {e}")
        return None


def _try_download(symbol, interval, period):
    for attempt in range(3):
        try:
            import yfinance as yf
            df = yf.download(symbol, period=period, interval=interval,
                             progress=False, auto_adjust=True, timeout=20)
            result = _clean(df, symbol, "download")
            if result is not None and len(result) > 50:
                return result
            time.sleep(2)
        except Exception as e:
            print(f"[WARN] download attempt {attempt+1} {symbol}: {e}")
            time.sleep(2)
    return None


def _clean(df, symbol, source):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if "Adj Close" in df.columns and "Close" not in df.columns:
        df.rename(columns={"Adj Close": "Close"}, inplace=True)
    required = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in required):
        return None
    df = df.dropna(subset=required).copy()
    print(f"[DATA] {symbol} {source}: {len(df)} bars ✓")
    return df