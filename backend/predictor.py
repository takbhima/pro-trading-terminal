"""
Prediction engine — combines technical analysis + news sentiment
to generate a directional forecast with confidence score.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.indicators import ema, rsi, atr, supertrend


def estimate_target_time(df: pd.DataFrame, entry: float, tp: float, interval: str) -> dict:
    """
    Estimate when the target price will be reached.
    Uses ATR as a proxy for expected movement per bar.
    """
    a_vals      = atr(df['High'], df['Low'], df['Close'], 14)
    atr_per_bar = float(a_vals.iloc[-20:].mean())
    if atr_per_bar <= 0:
        atr_per_bar = abs(tp - entry) * 0.1

    distance  = abs(tp - entry)
    bars_est  = max(1.0, (distance / atr_per_bar) * 1.4)  # 1.4x buffer

    mins_per_bar = {
        '1m': 1, '2m': 2, '5m': 5, '15m': 15, '30m': 30,
        '60m': 60, '1h': 60, '1d': 390, '1wk': 1950
    }.get(interval, 60)

    total_mins = bars_est * mins_per_bar

    # Human-readable label
    if   total_mins <=  15:  label = f"~{max(5, int(total_mins))} mins"
    elif total_mins <=  60:  label = f"~{int(total_mins)} mins"
    elif total_mins <= 120:  label = f"~{total_mins/60:.1f} hours"
    elif total_mins <= 390:  label = "by end of day"
    elif total_mins <= 780:  label = f"~{total_mins/390:.1f} trading days"
    elif total_mins <=1950:  label = f"~{int(total_mins/390)} trading days"
    else:                    label = f"~{int(total_mins/1950)} weeks"

    # Target datetime (skip weekends)
    dt = datetime.now() + timedelta(minutes=total_mins)
    for _ in range(7):
        if dt.weekday() < 5: break
        dt += timedelta(days=1)
    dt_str = dt.strftime('%d %b %H:%M') if interval not in ('1d','1wk') else dt.strftime('%d %b %Y')

    return {'label': label, 'datetime': dt_str, 'bars': round(bars_est, 1)}


def generate_prediction(df: pd.DataFrame, news_list: list, symbol: str, interval: str) -> dict:
    """
    Combine technical analysis + news sentiment into a prediction.
    Returns direction (BULLISH/BEARISH/NEUTRAL), confidence %, and reasoning.
    """
    c    = df['Close']
    h    = df['High']
    l    = df['Low']
    vol  = df['Volume'] if 'Volume' in df.columns else pd.Series(1, index=df.index)

    # Compute all indicators
    e9   = ema(c, 9);    e21  = ema(c, 21);   e50  = ema(c, 50)
    e200 = ema(c, 200);  r    = rsi(c, 14);    a    = atr(h, l, c, 14)
    st   = supertrend(h, l, c, 3, 10)
    macd_line = ema(c, 12) - ema(c, 26)
    macd_sig  = ema(macd_line, 9)
    bb_mid    = c.rolling(20).mean()
    bb_std    = c.rolling(20).std()
    bb_upper  = bb_mid + 2 * bb_std
    bb_lower  = bb_mid - 2 * bb_std

    # Current values (use last bar)
    cur = float(c.iloc[-1])
    v   = {
        'rsi'     : float(r.iloc[-1]),
        'e9'      : float(e9.iloc[-1]),
        'e21'     : float(e21.iloc[-1]),
        'e50'     : float(e50.iloc[-1]),
        'e200'    : float(e200.iloc[-1]),
        'st'      : float(st.iloc[-1]),
        'macd'    : float(macd_line.iloc[-1]),
        'msig'    : float(macd_sig.iloc[-1]),
        'atr'     : float(a.iloc[-20:].mean()),
        'vol'     : float(vol.iloc[-1]),
        'vol_ma'  : float(vol.rolling(20).mean().iloc[-1]),
        'bb_up'   : float(bb_upper.iloc[-1]),
        'bb_lo'   : float(bb_lower.iloc[-1]),
        'bb_mid'  : float(bb_mid.iloc[-1]),
        'chg_5'   : float((c.iloc[-1] / c.iloc[-6] - 1) * 100) if len(c) > 5 else 0,
    }

    # ── Technical Scoring ────────────────────────────────────────────────────
    score = 50
    bull_reasons = []
    bear_reasons = []

    # EMA stack
    if v['e9'] > v['e21'] > v['e50']:
        score += 14; bull_reasons.append('EMA 9 > 21 > 50 — strong uptrend alignment')
    elif v['e9'] < v['e21'] < v['e50']:
        score -= 14; bear_reasons.append('EMA 9 < 21 < 50 — strong downtrend alignment')
    elif v['e9'] > v['e21']:
        score += 7;  bull_reasons.append('EMA 9 above EMA 21 — short-term bullish')
    else:
        score -= 7;  bear_reasons.append('EMA 9 below EMA 21 — short-term bearish')

    # EMA 200 (long-term trend)
    if cur > v['e200']:
        score += 10; bull_reasons.append(f"Price above EMA 200 — long-term uptrend")
    else:
        score -= 10; bear_reasons.append(f"Price below EMA 200 — long-term downtrend")

    # RSI
    if v['rsi'] > 65:   score += 10; bull_reasons.append(f"RSI {v['rsi']:.0f} — strong bullish momentum")
    elif v['rsi'] > 55: score += 5;  bull_reasons.append(f"RSI {v['rsi']:.0f} — moderate bullish momentum")
    elif v['rsi'] < 35: score -= 10; bear_reasons.append(f"RSI {v['rsi']:.0f} — oversold / bearish momentum")
    elif v['rsi'] < 45: score -= 5;  bear_reasons.append(f"RSI {v['rsi']:.0f} — moderate bearish momentum")

    # Supertrend
    if v['st'] < 0:  score += 10; bull_reasons.append('Supertrend bullish — price above support line')
    else:            score -= 10; bear_reasons.append('Supertrend bearish — price below resistance line')

    # MACD
    if v['macd'] > v['msig']:  score += 8; bull_reasons.append('MACD above Signal line — bullish crossover')
    else:                       score -= 8; bear_reasons.append('MACD below Signal line — bearish crossover')

    # Bollinger Band position
    bb_pct = (cur - v['bb_lo']) / max(0.01, v['bb_up'] - v['bb_lo'])
    if bb_pct > 0.8:   bull_reasons.append(f"Price in upper BB zone — strong momentum")
    elif bb_pct < 0.2: bear_reasons.append(f"Price in lower BB zone — selling pressure")

    # 5-bar price change momentum
    if v['chg_5'] > 1.5:   score += 5;  bull_reasons.append(f"Strong 5-bar momentum +{v['chg_5']:.1f}%")
    elif v['chg_5'] < -1.5: score -= 5; bear_reasons.append(f"Weak 5-bar momentum {v['chg_5']:.1f}%")

    # Volume confirmation
    if v['vol'] > v['vol_ma'] * 1.4:
        lbl = 'Volume spike confirms bullish move' if score > 50 else 'Volume spike on bearish move — warning'
        if score > 50: bull_reasons.append(lbl)
        else:          bear_reasons.append(lbl)

    tech_score = max(5, min(95, score))

    # ── News Sentiment Scoring ───────────────────────────────────────────────
    news_delta = 0
    if news_list:
        for item in news_list[:10]:
            news_delta += item.get('score', 50) - 50
        news_delta /= min(10, len(news_list))
    news_score = max(5, min(95, 50 + news_delta))

    # Significant news events
    if news_delta > 15:  bull_reasons.append(f'News sentiment strongly positive ({len(news_list)} articles)')
    elif news_delta > 5: bull_reasons.append(f'News sentiment mildly positive')
    elif news_delta < -15: bear_reasons.append(f'News sentiment strongly negative ({len(news_list)} articles)')
    elif news_delta < -5:  bear_reasons.append(f'News sentiment mildly negative')

    # ── Final Combined Score ─────────────────────────────────────────────────
    final = tech_score * 0.70 + news_score * 0.30
    final = max(5, min(95, final))

    if final >= 60:   direction = 'BULLISH'
    elif final <= 40: direction = 'BEARISH'
    else:             direction = 'NEUTRAL'

    # Price targets
    if direction == 'BULLISH':
        tp1 = round(cur + v['atr'],       2)
        tp2 = round(cur + v['atr'] * 2.5, 2)
        sl  = round(cur - v['atr'],        2)
    elif direction == 'BEARISH':
        tp1 = round(cur - v['atr'],        2)
        tp2 = round(cur - v['atr'] * 2.5,  2)
        sl  = round(cur + v['atr'],         2)
    else:
        tp1 = round(cur + v['atr'] * 0.5, 2)
        tp2 = round(cur - v['atr'] * 0.5, 2)
        sl  = None

    return {
        'symbol'      : symbol,
        'direction'   : direction,
        'confidence'  : round(final, 1),
        'tech_score'  : round(tech_score, 1),
        'news_score'  : round(news_score, 1),
        'bull_reasons': bull_reasons,
        'bear_reasons': bear_reasons,
        'current'     : round(cur, 4),
        'tp1'         : tp1,
        'tp2'         : tp2,
        'sl'          : sl,
        'atr'         : round(v['atr'], 4),
        'rsi'         : round(v['rsi'], 2),
        'interval'    : interval,
    }