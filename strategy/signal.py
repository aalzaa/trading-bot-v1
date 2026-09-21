from __future__ import annotations

import pandas as pd


def generate_signal(
    row: pd.Series,
    min_score: float = 3.0,
) -> dict:
    """
    Generate the V1 order-flow signal.

    Existing signal components:
        - strong multi-bar CVD slope
        - delta
        - aggressive buy/sell ratio
        - big trade
        - VWAP

    New V1.1 component:
        - absorption proxy

    Absorption is intentionally used as a penalty,
    not as an absolute no-trade filter.

    BUY absorption:
        aggressive buyers appear absorbed
        -> penalize LONG

    SELL absorption:
        aggressive sellers appear absorbed
        -> penalize SHORT
    """

    score = 0.0
    reasons = []

    # =========================================================
    # FEATURE EXTRACTION
    # =========================================================

    volume_z = float(
        row.get("volume_z", 0.0)
    )

    delta_z = float(
        row.get("delta_z", 0.0)
    )

    cvd_slope_z = float(
        row.get("cvd_slope_z", 0.0)
    )

    buy_sell_ratio = float(
        row.get(
            "buy_sell_ratio",
            1.0,
        )
    )

    big_trade = bool(
        row.get(
            "big_trade",
            False,
        )
    )

    close = float(
        row.get(
            "close",
            0.0,
        )
    )

    vwap = float(
        row.get(
            "vwap",
            close,
        )
    )

    # New absorption features
    buy_absorption = bool(
        row.get(
            "buy_absorption",
            False,
        )
    )

    sell_absorption = bool(
        row.get(
            "sell_absorption",
            False,
        )
    )

    # =========================================================
    # VOLUME REMOVED FROM SIGNAL SCORING
    # =========================================================
    # Volume remains available as a raw/diagnostic feature, but it
    # no longer contributes to entry scoring.

    # =========================================================
    # DELTA
    # =========================================================

    if delta_z >= 1.0:
        score += 1.5
        reasons.append("delta_positive")

    elif delta_z <= -1.0:
        score -= 1.5
        reasons.append("delta_negative")

    # =========================================================
    # CVD
    # =========================================================
    # Strong CVD is now a mandatory directional entry filter.
    # The feature is a multi-bar CVD slope z-score.

    strong_cvd_long = cvd_slope_z >= 1.5
    strong_cvd_short = cvd_slope_z <= -1.5

    if strong_cvd_long:
        score += 1.5
        reasons.append("cvd_strong_positive")

    elif strong_cvd_short:
        score -= 1.5
        reasons.append("cvd_strong_negative")

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
    # ABSORPTION
    # =========================================================
    #
    # IMPORTANT:
    #
    # We do NOT immediately reverse the signal.
    #
    # We only penalize aggression that appears absorbed.
    #
    # BUY ABSORPTION:
    #     aggressive buying
    #     but insufficient price response
    #
    # SELL ABSORPTION:
    #     aggressive selling
    #     but insufficient price response
    #
    # This keeps the change conservative.
    # =========================================================

    if buy_absorption and score > 0:
        score -= 1.5
        reasons.append("buy_absorption")

    if sell_absorption and score < 0:
        score += 1.5
        reasons.append("sell_absorption")

    # =========================================================
    # FINAL SIGNAL
    # =========================================================
    # No trade unless CVD strongly agrees with the direction.

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