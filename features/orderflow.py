from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / std.replace(0, np.nan)


def _rolling_poc(df: pd.DataFrame, window: int = 48) -> pd.Series:
    """Approximate rolling POC using typical-price volume weighting."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
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

        poc.append((prices * volumes).sum() / volume_sum)

    return pd.Series(poc, index=df.index, dtype=float)


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    """UTC session VWAP."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    session = df.index.floor("D")
    pv = typical_price * df["volume"]

    cumulative_pv = pv.groupby(session).cumsum()
    cumulative_volume = df["volume"].groupby(session).cumsum()

    return cumulative_pv / cumulative_volume.replace(0, np.nan)


def add_absorption_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect a proxy for aggressive-flow absorption.

    This is not true order-book absorption because historical depth/
    replenishment data is unavailable.

    BUY_ABSORPTION:
        aggressive buying + high volume + weak upward price response

    SELL_ABSORPTION:
        aggressive selling + high volume + weak downward price response
    """
    df = df.copy()

    df["price_change"] = df["close"].pct_change()

    price_volatility = (
        df["price_change"].rolling(20).std().replace(0, np.nan)
    )

    df["price_response_z"] = df["price_change"] / price_volatility

    volume_safe = df["volume"].replace(0, np.nan)
    df["delta_pressure"] = df["delta"] / volume_safe
    df["delta_pressure_z"] = _safe_zscore(
        df["delta_pressure"],
        window=20,
    )

    strong_buy_pressure = df["delta_pressure_z"] >= 1.0
    strong_sell_pressure = df["delta_pressure_z"] <= -1.0
    high_volume = df["volume_z"] >= 1.0

    buy_price_failure = df["price_response_z"] <= 0.25
    sell_price_failure = df["price_response_z"] >= -0.25

    df["buy_absorption"] = (
        strong_buy_pressure & high_volume & buy_price_failure
    )
    df["sell_absorption"] = (
        strong_sell_pressure & high_volume & sell_price_failure
    )

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


def add_cvd_divergence_features(
    df: pd.DataFrame,
    lookback: int = 10,
) -> pd.DataFrame:
    """
    Detect price/CVD divergence over a rolling lookback.

    BULLISH_DIVERGENCE:
        price makes a lower low while CVD makes a higher low.
        This can support a long when the broader context is already long.

    BEARISH_DIVERGENCE:
        price makes a higher high while CVD makes a lower high.
        This can support a short when the broader context is already short.

    The divergence is deliberately treated as contextual confirmation,
    not as an automatic reversal signal.
    """
    df = df.copy()

    price_low = df["low"].rolling(lookback).min()
    price_high = df["high"].rolling(lookback).max()
    cvd_low = df["cvd"].rolling(lookback).min()
    cvd_high = df["cvd"].rolling(lookback).max()

    prev_price_low = price_low.shift(lookback)
    prev_price_high = price_high.shift(lookback)
    prev_cvd_low = cvd_low.shift(lookback)
    prev_cvd_high = cvd_high.shift(lookback)

    df["cvd_bullish_divergence"] = (
        (df["low"] < prev_price_low)
        & (df["cvd"] > prev_cvd_low)
    )

    df["cvd_bearish_divergence"] = (
        (df["high"] > prev_price_high)
        & (df["cvd"] < prev_cvd_high)
    )

    # Absorption in the opposite direction is contextual confirmation:
    # sellers absorbed while the broader flow is long -> long confirmation.
    # buyers absorbed while the broader flow is short -> short confirmation.
    df["cvd_long_confirmation"] = (
        df["cvd_bullish_divergence"]
        | (
            df["sell_absorption"]
            & (df["cvd_slope_z"] >= 0)
        )
    )

    df["cvd_short_confirmation"] = (
        df["cvd_bearish_divergence"]
        | (
            df["buy_absorption"]
            & (df["cvd_slope_z"] <= 0)
        )
    )

    df["cvd_divergence"] = np.select(
        [
            df["cvd_bullish_divergence"],
            df["cvd_bearish_divergence"],
        ],
        [
            "BULLISH",
            "BEARISH",
        ],
        default="NONE",
    )

    return df


def add_orderflow_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all derived order-flow research features."""
    df = df.copy()

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

    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing)
        )

    # CVD
    df["cvd"] = df["delta"].cumsum()

    # CVD trend over multiple bars.
    # Unlike CVD.diff(), this is not just the current bar's delta.
    df["cvd_slope"] = df["cvd"].diff(5)

    # Buy/sell ratio
    sell_volume_safe = df["sell_volume"].replace(0, np.nan)
    df["buy_sell_ratio"] = df["buy_volume"] / sell_volume_safe

    # Volume z-score
    df["volume_z"] = _safe_zscore(df["volume"], window=20)

    # Delta is retained as a raw input for absorption calculations,
    # but it is NOT an independent signal score anymore.
    df["delta_z"] = _safe_zscore(df["delta"], window=20)
    df["delta_pct"] = df["delta"] / df["volume"].replace(0, np.nan)

    # CVD trend z-score
    df["cvd_slope_z"] = _safe_zscore(df["cvd_slope"], window=20)

    # Big trade
    rolling_big_trade_threshold = (
        df["max_trade_size"].rolling(100).quantile(0.99)
    )
    df["big_trade"] = (
        df["max_trade_size"] >= rolling_big_trade_threshold
    )

    # Typical price / approximate POC
    df["typical_price"] = (
        df["high"] + df["low"] + df["close"]
    ) / 3.0

    df["poc"] = _rolling_poc(df, window=48)
    df["distance_to_poc"] = (
        (df["close"] - df["poc"])
        / df["poc"].replace(0, np.nan)
    )

    # Session VWAP
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Features require a DatetimeIndex.")

    df["vwap"] = _session_vwap(df)
    df["above_vwap"] = df["close"] > df["vwap"]
    df["below_vwap"] = df["close"] < df["vwap"]

    # Absorption proxy
    df = add_absorption_features(df)

    # CVD divergence / contextual confirmation
    df = add_cvd_divergence_features(df, lookback=10)

    required_feature_columns = [
        "volume_z",
        "cvd_slope_z",
        "buy_sell_ratio",
        "poc",
        "vwap",
        "price_response_z",
        "delta_pressure_z",
    ]

    return df.dropna(subset=required_feature_columns)
