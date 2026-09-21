from __future__ import annotations

import pandas as pd


def generate_signal(
    row: pd.Series,
    min_score: float = 3.0,
) -> dict:
    """Generate the V1 order-flow signal.

    This branch tests Delta +/-2.0 while keeping the CVD filter at +/-1.5.
    Volume remains excluded from scoring.
    """

    score = 0.0
    reasons = []

    delta_z = float(row.get("delta_z", 0.0))
    cvd_slope_z = float(row.get("cvd_slope_z", 0.0))
    buy_sell_ratio = float(row.get("buy_sell_ratio", 1.0))
    big_trade = bool(row.get("big_trade", False))
    close = float(row.get("close", 0.0))
    vwap = float(row.get("vwap", close))
    buy_absorption = bool(row.get("buy_absorption", False))
    sell_absorption = bool(row.get("sell_absorption", False))

    # Delta: stronger confirmation, +/-2.0 z-score.
    if delta_z >= 2.0:
        score += 1.5
        reasons.append("delta_strong_positive")
    elif delta_z <= -2.0:
        score -= 1.5
        reasons.append("delta_strong_negative")

    # CVD remains at +/-1.5 and is a mandatory directional filter.
    strong_cvd_long = cvd_slope_z >= 1.5
    strong_cvd_short = cvd_slope_z <= -1.5

    if strong_cvd_long:
        score += 1.5
        reasons.append("cvd_strong_positive")
    elif strong_cvd_short:
        score -= 1.5
        reasons.append("cvd_strong_negative")

    if buy_sell_ratio >= 1.5:
        score += 0.75
        reasons.append("aggressive_buyers")
    elif buy_sell_ratio <= 0.67:
        score -= 0.75
        reasons.append("aggressive_sellers")

    if big_trade:
        if score > 0:
            score += 0.5
            reasons.append("big_trade_buy")
        elif score < 0:
            score -= 0.5
            reasons.append("big_trade_sell")

    if close > vwap and score > 0:
        score += 0.5
        reasons.append("above_vwap")
    elif close < vwap and score < 0:
        score -= 0.5
        reasons.append("below_vwap")

    if buy_absorption and score > 0:
        score -= 1.5
        reasons.append("buy_absorption")

    if sell_absorption and score < 0:
        score += 1.5
        reasons.append("sell_absorption")

    if score >= min_score and strong_cvd_long:
        direction = "LONG"
    elif score <= -min_score and strong_cvd_short:
        direction = "SHORT"
    else:
        direction = "FLAT"

    return {
        "direction": direction,
        "score": score,
        "reasons": reasons,
        "buy_absorption": buy_absorption,
        "sell_absorption": sell_absorption,
    }
