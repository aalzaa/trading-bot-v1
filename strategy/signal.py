from __future__ import annotations

import pandas as pd


def generate_signal(
    row: pd.Series,
    min_score: float = 3.0,
) -> dict:
    """
    Generate the V1 CVD-focused order-flow signal.

    Signal components:
        - volume
        - CVD trend
        - aggressive buy/sell ratio
        - big trade
        - VWAP
        - CVD divergence / contextual absorption confirmation

    Delta is intentionally NOT scored independently because CVD is
    derived from delta. Delta remains available only for the absorption
    proxy in the feature layer.

    CVD divergence is contextual confirmation, not an automatic reversal:
        - bullish CVD divergence -> supports LONG
        - bearish CVD divergence -> supports SHORT
        - seller absorption in a long CVD context -> supports LONG
        - buyer absorption in a short CVD context -> supports SHORT
    """
    score = 0.0
    reasons = []

    volume_z = float(row.get("volume_z", 0.0))
    cvd_slope_z = float(row.get("cvd_slope_z", 0.0))
    buy_sell_ratio = float(row.get("buy_sell_ratio", 1.0))

    big_trade = bool(row.get("big_trade", False))

    close = float(row.get("close", 0.0))
    vwap = float(row.get("vwap", close))

    buy_absorption = bool(row.get("buy_absorption", False))
    sell_absorption = bool(row.get("sell_absorption", False))

    cvd_bullish_divergence = bool(
        row.get("cvd_bullish_divergence", False)
    )
    cvd_bearish_divergence = bool(
        row.get("cvd_bearish_divergence", False)
    )

    cvd_long_confirmation = bool(
        row.get("cvd_long_confirmation", False)
    )
    cvd_short_confirmation = bool(
        row.get("cvd_short_confirmation", False)
    )

    # =========================================================
    # VOLUME
    # =========================================================

    if volume_z >= 1.0:
        score += 0.5
        reasons.append("volume_high")

    # =========================================================
    # CVD
    # =========================================================

    if cvd_slope_z >= 0.5:
        score += 1.5
        reasons.append("cvd_positive")

    elif cvd_slope_z <= -0.5:
        score -= 1.5
        reasons.append("cvd_negative")

    # =========================================================
    # AGGRESSIVE BUY / SELL RATIO
    # =========================================================

    if buy_sell_ratio >= 1.5:
        score += 0.75
        reasons.append("aggressive_buyers")

    elif buy_sell_ratio <= 0.67:
        score -= 0.75
        reasons.append("aggressive_sellers")

    # =========================================================
    # BIG TRADE
    # =========================================================

    if big_trade:
        if score > 0:
            score += 0.5
            reasons.append("big_trade_buy")

        elif score < 0:
            score -= 0.5
            reasons.append("big_trade_sell")

    # =========================================================
    # VWAP
    # =========================================================

    if close > vwap and score > 0:
        score += 0.5
        reasons.append("above_vwap")

    elif close < vwap and score < 0:
        score -= 0.5
        reasons.append("below_vwap")

    # =========================================================
    # CVD DIVERGENCE / CONTEXTUAL CONFIRMATION
    # =========================================================

    # Bullish divergence:
    # price makes a lower low while CVD makes a higher low.
    if cvd_bullish_divergence and score > 0:
        score += 1.0
        reasons.append("cvd_bullish_divergence")

    # Bearish divergence:
    # price makes a higher high while CVD makes a lower high.
    if cvd_bearish_divergence and score < 0:
        score -= 1.0
        reasons.append("cvd_bearish_divergence")

    # Sellers absorbed while the broader CVD context is long.
    # This is the user's intended "short absorption = long confirmation".
    if (
        sell_absorption
        and cvd_long_confirmation
        and score > 0
    ):
        score += 1.0
        reasons.append("cvd_seller_absorption_long_confirmation")

    # Buyers absorbed while the broader CVD context is short.
    if (
        buy_absorption
        and cvd_short_confirmation
        and score < 0
    ):
        score -= 1.0
        reasons.append("cvd_buyer_absorption_short_confirmation")

    # =========================================================
    # ABSORPTION AGAINST THE TRADE
    # =========================================================

    # Aggressive buyers absorbed -> warning against LONG.
    if buy_absorption and score > 0:
        score -= 1.5
        reasons.append("buy_absorption")

    # Aggressive sellers absorbed -> warning against SHORT.
    if sell_absorption and score < 0:
        score += 1.5
        reasons.append("sell_absorption")

    # =========================================================
    # FINAL SIGNAL
    # =========================================================

    if score >= min_score:
        direction = "LONG"
    elif score <= -min_score:
        direction = "SHORT"
    else:
        direction = "FLAT"

    return {
        "direction": direction,
        "score": score,
        "reasons": reasons,
        "buy_absorption": buy_absorption,
        "sell_absorption": sell_absorption,
        "cvd_divergence": row.get("cvd_divergence", "NONE"),
        "cvd_long_confirmation": cvd_long_confirmation,
        "cvd_short_confirmation": cvd_short_confirmation,
    }
