def calculate_position_size(capital: float, risk_percent: float,
                            entry: float, stoploss: float) -> int:
    """
    Standard risk-based position sizing.
    quantity = (capital × risk%) / |entry - stoploss|
    """
    if entry == stoploss:
        return 0
    risk_amount = capital * (risk_percent / 100)
    per_unit_risk = abs(entry - stoploss)
    qty = risk_amount / per_unit_risk
    return max(1, int(qty))
