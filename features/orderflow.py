from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()

    return (series - mean) / std.replace(0, np.nan)


def _rolling_poc(df: pd.DataFrame, window: int = 48) -> pd.Series:
    """
    Approximate rolling POC using the typical price of each bar.

    This is NOT a true historical volume-at-price profile because
    we do not retain volume at every price level.
    """

    typical_price = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3.0

    poc = []

    for i in range(len(df)):
        start = max(0, i - window + 1)

        prices = typical_price.iloc[start:i + 1]
        volumes = df["volume"].iloc[start:i + 1]

        if prices.empty:
            poc.append(np.nan)
            continue

        volume_sum = volumes.sum()

        if volume_sum <= 0:
            poc.append(prices.iloc[-1])
            continue

        weighted_price = (
            (prices * volumes).sum()
            / volume_sum
        )

        poc.append(weighted_price)

    return pd.Series(
        poc,
        index=df.index,
        dtype=float,
    )


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    """
    UTC session VWAP.
    """

    typical_price = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3.0

    session = df.index.floor("D")

    pv = typical_price * df["volume"]

    cumulative_pv = pv.groupby(session).cumsum()
    cumulative_volume = (
        df["volume"]
        .groupby(session)
        .cumsum()
    )

    return cumulative_pv / cumulative_volume.replace(
        0,
        np.nan,
    )


def add_absorption_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Detect a proxy for aggressive-flow absorption.

    We do NOT have historical order-book depth, so this is not
    true bid/ask absorption.

    Logic:

    BUY ABSORPTION
        strong positive aggressive delta
        + elevated volume
        + price fails to respond upward

    SELL ABSORPTION
        strong negative aggressive delta
        + elevated volume
        + price fails to respond downward

    The purpose is to identify situations where aggressive
    market orders appear to have little immediate price impact.
    """

    df = df.copy()

    # ---------------------------------------------------------
    # BASIC PRICE RESPONSE
    # ---------------------------------------------------------

    df["price_change"] = (
        df["close"].pct_change()
    )

    price_volatility = (
        df["price_change"]
        .rolling(20)
        .std()
        .replace(0, np.nan)
    )

    df["price_response_z"] = (
        df["price_change"]
        / price_volatility
    )

    # ---------------------------------------------------------
    # DELTA PRESSURE
    # ---------------------------------------------------------

    volume_safe = df["volume"].replace(
        0,
        np.nan,
    )

    df["delta_pressure"] = (
        df["delta"]
        / volume_safe
    )

    df["delta_pressure_z"] = _safe_zscore(
        df["delta_pressure"],
        window=20,
    )

    # ---------------------------------------------------------
    # ABSORPTION CONDITIONS
    # ---------------------------------------------------------

    strong_buy_pressure = (
        df["delta_pressure_z"] >= 1.0
    )

    strong_sell_pressure = (
        df["delta_pressure_z"] <= -1.0
    )

    high_volume = (
        df["volume_z"] >= 1.0
    )

    # Buyers are aggressive but price does not respond upward.
    buy_price_failure = (
        df["price_response_z"] <= 0.25
    )

    # Sellers are aggressive but price does not respond downward.
    sell_price_failure = (
        df["price_response_z"] >= -0.25
    )

    df["buy_absorption"] = (
        strong_buy_pressure
        & high_volume
        & buy_price_failure
    )

    df["sell_absorption"] = (
        strong_sell_pressure
        & high_volume
        & sell_price_failure
    )

    # ---------------------------------------------------------
    # ABSORPTION LABEL
    # ---------------------------------------------------------

    df["absorption"] = np.select(
        [
            df["buy_absorption"],
            df["sell_absorption"],
        ],
        [
            "BUY_ABSORPTION",
            "SELL_ABSORPTION",
        ],
        default="NONE",
    )

    # Numeric representation useful for diagnostics.
    df["absorption_score"] = np.select(
        [
            df["buy_absorption"],
            df["sell_absorption"],
        ],
        [
            -1.0,
            1.0,
        ],
        default=0.0,
    )

    return df


def add_orderflow_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build all derived order-flow features.

    The data layer supplies raw/aggregated trade information.
    This module owns the derived research features.
    """

    df = df.copy()

    # ---------------------------------------------------------
    # BASIC SAFETY
    # ---------------------------------------------------------

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "buy_volume",
        "sell_volume",
        "delta",
        "trade_count",
        "max_trade_size",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing)
        )

    # ---------------------------------------------------------
    # CVD
    # ---------------------------------------------------------

    df["cvd"] = df["delta"].cumsum()

    df["cvd_change"] = (
        df["cvd"]
        .diff()
    )

    # Multi-bar CVD slope: avoids making CVD slope identical to
    # the current bar's delta.
    df["cvd_slope"] = (
        df["cvd"]
        .diff(5)
    )

    # ---------------------------------------------------------
    # BUY / SELL RATIO
    # ---------------------------------------------------------

    sell_volume_safe = (
        df["sell_volume"]
        .replace(0, np.nan)
    )

    df["buy_sell_ratio"] = (
        df["buy_volume"]
        / sell_volume_safe
    )

    # ---------------------------------------------------------
    # VOLUME Z-SCORE
    # ---------------------------------------------------------

    df["volume_z"] = _safe_zscore(
        df["volume"],
        window=20,
    )

    # ---------------------------------------------------------
    # DELTA Z-SCORE
    # ---------------------------------------------------------

    df["delta_z"] = _safe_zscore(
        df["delta"],
        window=20,
    )

    # Delta as percentage of total volume.
    df["delta_pct"] = (
        df["delta"]
        / df["volume"].replace(0, np.nan)
    )

    # ---------------------------------------------------------
    # CVD SLOPE Z-SCORE
    # ---------------------------------------------------------

    df["cvd_slope_z"] = _safe_zscore(
        df["cvd_slope"],
        window=20,
    )

    # ---------------------------------------------------------
    # BIG TRADE
    # ---------------------------------------------------------

    rolling_big_trade_threshold = (
        df["max_trade_size"]
        .rolling(100)
        .quantile(0.99)
    )

    df["big_trade"] = (
        df["max_trade_size"]
        >= rolling_big_trade_threshold
    )

    # ---------------------------------------------------------
    # TYPICAL PRICE
    # ---------------------------------------------------------

    df["typical_price"] = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3.0

    # ---------------------------------------------------------
    # APPROXIMATE ROLLING POC
    # ---------------------------------------------------------

    df["poc"] = _rolling_poc(
        df,
        window=48,
    )

    df["distance_to_poc"] = (
        (
            df["close"]
            - df["poc"]
        )
        / df["poc"].replace(0, np.nan)
    )

    # ---------------------------------------------------------
    # SESSION VWAP
    # ---------------------------------------------------------

    # Make sure the index is datetime.
    if not isinstance(
        df.index,
        pd.DatetimeIndex,
    ):
        raise ValueError(
            "Features require a DatetimeIndex."
        )

    df["vwap"] = _session_vwap(df)

    df["above_vwap"] = (
        df["close"] > df["vwap"]
    )

    df["below_vwap"] = (
        df["close"] < df["vwap"]
    )

    # ---------------------------------------------------------
    # ABSORPTION PROXY
    # ---------------------------------------------------------

    df = add_absorption_features(df)

    # ---------------------------------------------------------
    # REMOVE INVALID FEATURE ROWS
    # ---------------------------------------------------------

    required_feature_columns = [
        "volume_z",
        "delta_z",
        "cvd_slope_z",
        "buy_sell_ratio",
        "poc",
        "vwap",
        "price_response_z",
        "delta_pressure_z",
    ]

    df = df.dropna(
        subset=required_feature_columns
    )

    return df