def calculate_position_size(capital, risk_percent, entry, stoploss):
    risk_amount = capital * (risk_percent / 100)
    per_share_risk = abs(entry - stoploss)
    qty = risk_amount / per_share_risk if per_share_risk > 0 else 0
    return round(qty)
