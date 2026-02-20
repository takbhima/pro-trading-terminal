"""
Trading strategies — all compute signals inline with direct index access.
This guarantees timestamps always match the chart candles exactly.
"""
import pandas as pd
import numpy as np
from backend.indicators import ema, rsi, atr, supertrend, crossover, crossunder


# ─────────────────────────────────────────────────────────────────────
#  INTERNAL HELPER
# ─────────────────────────────────────────────────────────────────────
def _build_signal(df: pd.DataFrame, i: int, typ: str,
                  a_series: pd.Series, r_series: pd.Series,
                  ts_fn) -> dict:
    close = float(df['Close'].iloc[i])
    av    = float(a_series.iloc[i])
    rv    = float(r_series.iloc[i])
    return {
        'time' : ts_fn(df.index[i]),
        'type' : typ,
        'price': round(close, 4),
        'sl'   : round(close - av, 4)       if typ == 'BUY' else round(close + av, 4),
        'tp'   : round(close + av * 2.0, 4) if typ == 'BUY' else round(close - av * 2.0, 4),
        'rsi'  : round(rv, 2),
        'atr'  : round(av, 4),
    }


# ─────────────────────────────────────────────────────────────────────
#  STRATEGY 1 — Pro MTF  (swing, 1-3 signals)
#  EMA 9/21 crossover + RSI 50 + EMA 200 trend + Supertrend confirm
# ─────────────────────────────────────────────────────────────────────
def strategy_pro_mtf(df: pd.DataFrame, ts_fn) -> list:
    c   = df['Close']
    e9  = ema(c, 9);  e21 = ema(c, 21);  e200 = ema(c, 200)
    r   = rsi(c, 14); a   = atr(df['High'], df['Low'], c, 14)
    st  = supertrend(df['High'], df['Low'], c, 3, 10)
    cu  = crossover(e9, e21);  cd = crossunder(e9, e21)

    out = []
    for i in range(1, len(df)):
        price = float(c.iloc[i])
        if cu.iloc[i] and r.iloc[i] > 50 and price > e200.iloc[i] and st.iloc[i] < 0:
            out.append(_build_signal(df, i, 'BUY',  a, r, ts_fn))
        elif cd.iloc[i] and r.iloc[i] < 50 and price < e200.iloc[i] and st.iloc[i] > 0:
            out.append(_build_signal(df, i, 'SELL', a, r, ts_fn))
    return out


# ─────────────────────────────────────────────────────────────────────
#  STRATEGY 2 — VWAP + EMA  (intraday, 4-6 signals)
#  Price vs VWAP crossover + EMA 9/21 direction + RSI momentum
# ─────────────────────────────────────────────────────────────────────
def strategy_vwap_ema(df: pd.DataFrame, ts_fn) -> list:
    c     = df['Close']
    tp    = (df['High'] + df['Low'] + c) / 3
    vwap  = (tp * df['Volume']).cumsum() / df['Volume'].replace(0, np.nan).cumsum()
    e9    = ema(c, 9);  e21 = ema(c, 21)
    r     = rsi(c, 14); a   = atr(df['High'], df['Low'], c, 14)
    cv_up = crossover(c, vwap);  cv_dn = crossunder(c, vwap)

    out = []
    for i in range(1, len(df)):
        if cv_up.iloc[i] and e9.iloc[i] > e21.iloc[i] and r.iloc[i] > 50:
            out.append(_build_signal(df, i, 'BUY',  a, r, ts_fn))
        elif cv_dn.iloc[i] and e9.iloc[i] < e21.iloc[i] and r.iloc[i] < 50:
            out.append(_build_signal(df, i, 'SELL', a, r, ts_fn))
    return out


# ─────────────────────────────────────────────────────────────────────
#  STRATEGY 3 — RSI Reversal  (mean reversion, 3-6 signals)
#  RSI exits oversold/overbought + EMA 50 trend filter
# ─────────────────────────────────────────────────────────────────────
def strategy_rsi_reversal(df: pd.DataFrame, ts_fn) -> list:
    c    = df['Close']
    r    = rsi(c, 14);  a = atr(df['High'], df['Low'], c, 14)
    e50  = ema(c, 50)
    rp   = r.shift(1).fillna(50)

    # RSI crosses 30 upward (exit oversold → BUY)
    # RSI crosses 70 downward (exit overbought → SELL)
    cross30_up   = (rp < 30) & (r >= 30)
    cross70_down = (rp > 70) & (r <= 70)

    out = []
    for i in range(1, len(df)):
        price = float(c.iloc[i])
        if cross30_up.iloc[i] and price > e50.iloc[i]:
            out.append(_build_signal(df, i, 'BUY',  a, r, ts_fn))
        elif cross70_down.iloc[i] and price < e50.iloc[i]:
            out.append(_build_signal(df, i, 'SELL', a, r, ts_fn))
    return out


# ─────────────────────────────────────────────────────────────────────
#  STRATEGY 4 — Bollinger Breakout  (momentum, 4-6 signals)
#  Price breaks Bollinger Band + RSI + volume confirmation
# ─────────────────────────────────────────────────────────────────────
def strategy_bollinger(df: pd.DataFrame, ts_fn) -> list:
    c     = df['Close']
    sma   = c.rolling(20).mean()
    std   = c.rolling(20).std()
    upper = sma + 2 * std;  lower = sma - 2 * std
    r     = rsi(c, 14);     a     = atr(df['High'], df['Low'], c, 14)
    vm    = df['Volume'].rolling(20).mean()
    c_p   = c.shift(1);  up_p = upper.shift(1);  lo_p = lower.shift(1)

    out = []
    for i in range(20, len(df)):
        price  = float(c.iloc[i])
        vol_ok = float(df['Volume'].iloc[i]) > float(vm.iloc[i]) * 1.3
        if float(c_p.iloc[i]) <= float(up_p.iloc[i]) and price > float(upper.iloc[i]) and r.iloc[i] > 55 and vol_ok:
            out.append(_build_signal(df, i, 'BUY',  a, r, ts_fn))
        elif float(c_p.iloc[i]) >= float(lo_p.iloc[i]) and price < float(lower.iloc[i]) and r.iloc[i] < 45 and vol_ok:
            out.append(_build_signal(df, i, 'SELL', a, r, ts_fn))
    return out


# ─────────────────────────────────────────────────────────────────────
#  STRATEGY 5 — MACD Crossover  (trend, 4-6 signals)
#  MACD/Signal cross + histogram confirm + RSI filter
# ─────────────────────────────────────────────────────────────────────
def strategy_macd(df: pd.DataFrame, ts_fn) -> list:
    c      = df['Close']
    macd   = ema(c, 12) - ema(c, 26)
    signal = ema(macd, 9)
    hist   = macd - signal
    r      = rsi(c, 14);  a = atr(df['High'], df['Low'], c, 14)
    e50    = ema(c, 50)
    cu_m   = crossover(macd, signal);  cd_m = crossunder(macd, signal)

    out = []
    for i in range(1, len(df)):
        price = float(c.iloc[i])
        if cu_m.iloc[i] and hist.iloc[i] > 0 and r.iloc[i] > 50:
            out.append(_build_signal(df, i, 'BUY',  a, r, ts_fn))
        elif cd_m.iloc[i] and hist.iloc[i] < 0 and r.iloc[i] < 50:
            out.append(_build_signal(df, i, 'SELL', a, r, ts_fn))
    return out


# ─────────────────────────────────────────────────────────────────────
#  STRATEGY 6 — Supertrend Scalper  (aggressive, 6-12 signals)
#  Fast Supertrend(2,7) flip with RSI confirmation
# ─────────────────────────────────────────────────────────────────────
def strategy_supertrend_scalper(df: pd.DataFrame, ts_fn) -> list:
    c    = df['Close']
    st_f = supertrend(df['High'], df['Low'], c, 2.0, 7)
    r    = rsi(c, 14);  a = atr(df['High'], df['Low'], c, 14)
    st_p = st_f.shift(1)

    out = []
    for i in range(1, len(df)):
        if st_p.iloc[i] > 0 and st_f.iloc[i] < 0 and r.iloc[i] > 45:  # flipped bullish
            out.append(_build_signal(df, i, 'BUY',  a, r, ts_fn))
        elif st_p.iloc[i] < 0 and st_f.iloc[i] > 0 and r.iloc[i] < 55:  # flipped bearish
            out.append(_build_signal(df, i, 'SELL', a, r, ts_fn))
    return out


# ─────────────────────────────────────────────────────────────────────
#  REGISTRY
# ─────────────────────────────────────────────────────────────────────
STRATEGIES = {
    'pro_mtf': {
        'fn'         : strategy_pro_mtf,
        'name'       : 'Pro MTF',
        'description': 'EMA 9/21 cross + RSI + EMA 200 trend + Supertrend. Best for swing trading.',
        'signals_day': '1–3',
        'best_for'   : '1D, 1W',
        'style'      : 'Swing',
        'color'      : '#3b82f6',
    },
    'vwap_ema': {
        'fn'         : strategy_vwap_ema,
        'name'       : 'VWAP + EMA',
        'description': 'Price vs VWAP crossover + EMA 9/21 direction + RSI. Classic intraday.',
        'signals_day': '4–6',
        'best_for'   : '5m, 15m',
        'style'      : 'Intraday',
        'color'      : '#00d084',
    },
    'rsi_reversal': {
        'fn'         : strategy_rsi_reversal,
        'name'       : 'RSI Reversal',
        'description': 'RSI exits oversold (<30) or overbought (>70) zones with EMA 50 filter.',
        'signals_day': '3–6',
        'best_for'   : '5m, 15m',
        'style'      : 'Mean Reversion',
        'color'      : '#a78bfa',
    },
    'bollinger': {
        'fn'         : strategy_bollinger,
        'name'       : 'Bollinger Breakout',
        'description': 'Price breaks Bollinger Band + RSI momentum + volume spike confirmation.',
        'signals_day': '4–6',
        'best_for'   : '5m, 15m',
        'style'      : 'Breakout',
        'color'      : '#f0b429',
    },
    'macd': {
        'fn'         : strategy_macd,
        'name'       : 'MACD Crossover',
        'description': 'MACD crosses Signal line + histogram confirms + RSI filter.',
        'signals_day': '4–6',
        'best_for'   : '15m, 1H',
        'style'      : 'Trend',
        'color'      : '#fb7185',
    },
    'supertrend_scalper': {
        'fn'         : strategy_supertrend_scalper,
        'name'       : 'ST Scalper',
        'description': 'Fast Supertrend(2,7) direction flip + RSI confirmation. Most signals.',
        'signals_day': '6–12',
        'best_for'   : '5m',
        'style'      : 'Scalping',
        'color'      : '#f97316',
    },
}

def list_strategies() -> list:
    return [{'key': k, **{x: v[x] for x in ['name','description','signals_day','best_for','style','color']}}
            for k, v in STRATEGIES.items()]