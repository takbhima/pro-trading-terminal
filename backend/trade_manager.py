"""
Trade Manager — Single Active Trade System
==========================================
Implements all exit conditions from Req_01.md:
  A) Target Hit
  B) Stop Loss Hit
  C) Time-based Exit  (entry_time + expected_bars × interval_minutes)
  D) EOD Exit         (15:20 IST for NSE, 15:55 EST for US)

One active trade per symbol at a time.
Trades are in-memory (reset on server restart — by design for intraday).
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

_IST = pytz.timezone('Asia/Kolkata')
_EST = pytz.timezone('America/New_York')

# Minutes per interval — used for time-based exit
_INTERVAL_MINUTES = {
    '1m': 1, '2m': 2, '5m': 5, '15m': 15, '30m': 30,
    '60m': 60, '1h': 60, '1d': 390, '1wk': 1950,
}

# EOD cutoff times (hour, minute) in each market's local timezone
_EOD = {
    'NSE' : (_IST, 15, 20),   # 3:20 PM IST
    'NYSE': (_EST, 15, 55),   # 3:55 PM EST
}


def _is_nse_symbol(sym: str) -> bool:
    return sym.endswith('.NS') or sym.endswith('.BO') or sym in ('^NSEI', '^NSEBANK', '^BSESN')


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_minutes(entry_time: datetime) -> float:
    return (_now_utc() - entry_time).total_seconds() / 60


def _compute_confidence(rsi: float, signal_type: str) -> float:
    """
    Confidence 0–100 based on RSI distance from neutral (50).
    BUY  → higher RSI above 50 = higher confidence (capped at 50+45=95)
    SELL → lower RSI below 50 = higher confidence
    """
    if signal_type == 'BUY':
        dist = max(0.0, rsi - 50.0)
    else:
        dist = max(0.0, 50.0 - rsi)
    return round(min(95.0, 50.0 + dist * 1.8), 1)


class TradeManager:
    """
    Manages active trades across all symbols.
    Thread-safe enough for single-process asyncio server.
    """

    def __init__(self):
        # {symbol: trade_dict}
        self._active: dict = {}
        # {symbol: [closed_trade, ...]}  — last 20 per symbol
        self._history: dict = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def open_trade(self, signal: dict, symbol: str,
                   strategy: str, interval: str) -> Optional[dict]:
        """
        Open a new trade from a strategy signal.
        Returns the trade dict, or None if a trade is already active for symbol.

        signal must have: type, price, sl, tp, rsi, atr, target_bars (optional)
        """
        if symbol in self._active:
            return None   # one trade per symbol — ignore new signal

        iv_min  = _INTERVAL_MINUTES.get(interval, 5)
        bars    = float(signal.get('target_bars') or signal.get('bars') or 5)
        exp_min = bars * iv_min

        confidence = _compute_confidence(
            float(signal.get('rsi', 50)), signal['type']
        )

        trade = {
            'symbol'                : symbol,
            'timeframe'             : interval,
            'strategy'              : strategy,
            'side'                  : signal['type'],          # 'BUY' | 'SELL'
            'entry_price'           : round(float(signal['price']), 4),
            'target_price'          : round(float(signal['tp']),    4),
            'stop_loss'             : round(float(signal['sl']),    4),
            'confidence'            : confidence,
            'entry_time'            : _now_utc().isoformat(),
            'entry_time_dt'         : _now_utc(),              # internal datetime obj
            'expected_time_minutes' : round(exp_min, 1),
            'expected_bars'         : round(bars, 1),
            'rsi'                   : round(float(signal.get('rsi', 50)), 2),
            'atr'                   : round(float(signal.get('atr', 0)),  4),
            'status'                : 'ACTIVE',
        }

        self._active[symbol] = trade
        return trade

    def check_exits(self, current_price: float, symbol: str) -> Optional[dict]:
        """
        Check all exit conditions for an active trade.
        Returns exit event dict if trade closed, else None.
        Must be called on every price tick.
        """
        trade = self._active.get(symbol)
        if not trade:
            return None

        price  = float(current_price)
        side   = trade['side']
        entry  = trade['entry_price']
        tp     = trade['target_price']
        sl     = trade['stop_loss']
        et     = trade['entry_time_dt']
        exp_m  = trade['expected_time_minutes']

        reason = None

        # ── A) Target Hit ────────────────────────────────────────────────────
        if side == 'BUY'  and price >= tp:  reason = 'Target Hit'
        if side == 'SELL' and price <= tp:  reason = 'Target Hit'

        # ── B) Stop Loss Hit ─────────────────────────────────────────────────
        if reason is None:
            if side == 'BUY'  and price <= sl: reason = 'Stop Hit'
            if side == 'SELL' and price >= sl: reason = 'Stop Hit'

        # ── C) Time-Based Exit ───────────────────────────────────────────────
        if reason is None:
            elapsed = _elapsed_minutes(et)
            if elapsed >= exp_m:
                reason = 'Time Exit'

        # ── D) EOD Exit ──────────────────────────────────────────────────────
        if reason is None:
            reason = self._check_eod(symbol)

        if reason:
            return self._close_trade(symbol, price, reason)
        return None

    def force_close(self, symbol: str, price: float,
                    reason: str = 'Manual Close') -> Optional[dict]:
        """Manually close a trade (e.g., user button or EOD sweep)."""
        if symbol not in self._active:
            return None
        return self._close_trade(symbol, price, reason)

    def get_active(self, symbol: str) -> Optional[dict]:
        """Return active trade for symbol, or None."""
        t = self._active.get(symbol)
        if not t:
            return None
        # Return a copy with live elapsed minutes added
        result = {**t}
        result.pop('entry_time_dt', None)   # not JSON-serialisable
        result['elapsed_minutes'] = round(_elapsed_minutes(t['entry_time_dt']), 1)
        return result

    def get_all_active(self) -> list:
        """Return list of all active trades (without internal datetime obj)."""
        out = []
        for sym, t in self._active.items():
            r = {**t}
            r.pop('entry_time_dt', None)
            r['elapsed_minutes'] = round(_elapsed_minutes(t['entry_time_dt']), 1)
            out.append(r)
        return out

    def get_history(self, symbol: str = None) -> list:
        """Return closed trade history for a symbol (or all symbols)."""
        if symbol:
            return list(reversed(self._history.get(symbol, [])))
        out = []
        for trades in self._history.values():
            out.extend(trades)
        out.sort(key=lambda x: x.get('exit_time',''), reverse=True)
        return out[:100]

    def eod_sweep(self) -> list:
        """
        Force-close all active trades at EOD.
        Returns list of exit events. Call from the 5-min WS loop.
        """
        import yfinance as yf
        events = []
        for sym in list(self._active.keys()):
            reason = self._check_eod(sym)
            if reason:
                # Try to get current price; fall back to entry price
                try:
                    info  = yf.Ticker(sym).fast_info
                    price = float(getattr(info,'last_price',None) or
                                  getattr(info,'regular_market_price',None) or
                                  self._active[sym]['entry_price'])
                except Exception:
                    price = self._active[sym]['entry_price']
                ev = self._close_trade(sym, price, reason)
                if ev:
                    events.append(ev)
        return events

    # ── Internal ─────────────────────────────────────────────────────────────

    def _close_trade(self, symbol: str, exit_price: float, reason: str) -> dict:
        trade = self._active.pop(symbol, None)
        if not trade:
            return {}

        entry    = trade['entry_price']
        side     = trade['side']
        elapsed  = _elapsed_minutes(trade['entry_time_dt'])

        # PnL: positive = profit, negative = loss
        if side == 'BUY':
            pnl = round(exit_price - entry, 4)
        else:
            pnl = round(entry - exit_price, 4)

        pnl_pct = round((pnl / entry) * 100, 2) if entry else 0

        event = {
            'type'             : 'exit',
            'symbol'           : symbol,
            'side'             : side,
            'strategy'         : trade['strategy'],
            'timeframe'        : trade['timeframe'],
            'entry_price'      : entry,
            'exit_price'       : round(exit_price, 4),
            'target_price'     : trade['target_price'],
            'stop_loss'        : trade['stop_loss'],
            'exit_reason'      : reason,
            'pnl'              : pnl,
            'pnl_pct'          : pnl_pct,
            'duration_minutes' : round(elapsed, 1),
            'entry_time'       : trade['entry_time'],
            'exit_time'        : _now_utc().isoformat(),
            'confidence'       : trade['confidence'],
        }

        # Store in history
        if symbol not in self._history:
            self._history[symbol] = []
        self._history[symbol].insert(0, event)
        if len(self._history[symbol]) > 20:
            self._history[symbol].pop()

        return event

    def _check_eod(self, symbol: str) -> Optional[str]:
        """Return 'EOD Exit' if current time is past EOD cutoff for this symbol."""
        now = _now_utc()
        if _is_nse_symbol(symbol):
            tz, h, m = _EOD['NSE']
        else:
            tz, h, m = _EOD['NYSE']

        local = now.astimezone(tz)
        cutoff = local.replace(hour=h, minute=m, second=0, microsecond=0)

        # Only trigger on weekdays
        if local.weekday() < 5 and local >= cutoff:
            return 'EOD Exit'
        return None
