def calculate_position_size(capital, risk_percent, entry, stoploss):
    risk_amount = capital * (risk_percent / 100)
    per_unit_risk = abs(entry - stoploss)

    if per_unit_risk == 0:
        return 0

    quantity = risk_amount / per_unit_risk
    return round(quantity, 2)
