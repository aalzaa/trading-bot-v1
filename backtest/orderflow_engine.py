from __future__ import annotations

import math
import pandas as pd

from strategy.signal import generate_signal


FIXED_RR_VALUES = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)


def run_backtest(
    df: pd.DataFrame,
    initial_equity: float = 10_000,
    risk_fraction: float = 0.005,
    stop_pct: float = 0.0025,
    rr_values=FIXED_RR_VALUES,
    min_score: float = 3.0,
    cooldown_bars: int = 2,
):
    results = {
        str(rr): _single_fixed(
            df,
            initial_equity,
            risk_fraction,
            stop_pct,
            rr,
            min_score,
            cooldown_bars,
        )
        for rr in rr_values
    }

    results["structure_trailing"] = _single_structure(
        df,
        initial_equity,
        risk_fraction,
        stop_pct,
        min_score,
        cooldown_bars,
    )

    return results


def _risk_position(
    entry: float,
    stop_distance: float,
    equity: float,
    risk_fraction: float,
) -> float:
    risk_cash = equity * risk_fraction
    return risk_cash / stop_distance if stop_distance > 0 else 0.0


def _stats(initial_equity, equity, trades, extra=None):
    pnls = [t["pnl"] for t in trades]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    pf = gross_profit / gross_loss if gross_loss else math.inf

    out = {
        "initial_equity": initial_equity,
        "final_equity": equity,
        "return_pct": (equity / initial_equity - 1) * 100,
        "trades": len(trades),
        "win_rate_pct": (
            len(wins) / len(trades) * 100
            if trades
            else 0.0
        ),
        "expectancy": (
            sum(pnls) / len(pnls)
            if pnls
            else 0.0
        ),
        "profit_factor": pf,
        "max_drawdown_pct": max(
            (t["drawdown"] for t in trades),
            default=0.0,
        ),
        "trade_log": trades,
    }

    if extra:
        out.update(extra)

    return out


def _feature_snapshot(row: pd.Series) -> dict:
    """Capture only information available on the signal bar."""

    def val(name, default=None):
        value = row.get(name, default)

        if pd.isna(value) if value is not None else False:
            return None

        return value

    cvd = val("cvd_slope_z")

    return {
        "volume_z": val("volume_z"),
        "cvd_slope_z": cvd,

        "cvd_condition": (
            "UP"
            if cvd is not None and float(cvd) >= 0.5
            else "DOWN"
            if cvd is not None and float(cvd) <= -0.5
            else "NEUTRAL"
        ),

        "buy_sell_ratio": val("buy_sell_ratio"),
        "big_trade": val("big_trade", False),
        "vwap": val("vwap"),
        "distance_to_poc": val("distance_to_poc"),

        # Absorption telemetry
        "absorption": val("absorption"),
        "absorption_score": val("absorption_score", 0),
        "cvd_divergence": val("cvd_divergence", "NONE"),
        "cvd_bullish_divergence": val("cvd_bullish_divergence", False),
        "cvd_bearish_divergence": val("cvd_bearish_divergence", False),
        "cvd_long_confirmation": val("cvd_long_confirmation", False),
        "cvd_short_confirmation": val("cvd_short_confirmation", False),
    }


def _update_excursions(
    entry: float,
    side: int,
    stop_distance: float,
    high: float,
    low: float,
    max_favorable_r: float,
    max_adverse_r: float,
):
    favorable = (
        high - entry
        if side == 1
        else entry - low
    )

    adverse = (
        entry - low
        if side == 1
        else high - entry
    )

    max_favorable_r = max(
        max_favorable_r,
        favorable / stop_distance,
    )

    max_adverse_r = max(
        max_adverse_r,
        adverse / stop_distance,
    )

    return max_favorable_r, max_adverse_r


def _base_trade(
    df: pd.DataFrame,
    signal_index: int,
    exit_index: int,
    signal: str,
    score: float,
    reasons: dict,
    entry: float,
    exit_price: float,
    pnl: float,
    outcome: str,
    rr_model,
    drawdown: float,
    stop_distance: float,
    max_favorable_r: float,
    max_adverse_r: float,
    exit_reason: str,
    initial_risk_cash: float,
    extra: dict | None = None,
):
    signal_ts = df.index[signal_index]
    entry_ts = df.index[signal_index + 1]
    exit_ts = df.index[exit_index]

    duration_minutes = max(
        1.0,
        (exit_ts - entry_ts).total_seconds() / 60.0,
    )

    trade = {
        "timestamp": str(signal_ts),
        "signal_timestamp": str(signal_ts),
        "entry_timestamp": str(entry_ts),
        "exit_timestamp": str(exit_ts),

        "signal": signal,
        "direction": signal,

        "score": score,
        "reasons": reasons,

        "entry": entry,
        "exit": exit_price,

        "pnl": pnl,
        "outcome": outcome,

        "duration_bars": max(
            1,
            exit_index - signal_index,
        ),

        "duration_minutes": duration_minutes,

        "mfe_r": max_favorable_r,
        "mae_r": max_adverse_r,

        "rr_realized": (
            pnl / initial_risk_cash
            if initial_risk_cash
            else 0.0
        ),

        "rr_model": rr_model,
        "exit_reason": exit_reason,
        "drawdown": drawdown,
    }

    trade.update(
        _feature_snapshot(
            df.iloc[signal_index]
        )
    )

    if extra:
        trade.update(extra)

    return trade


def _single_fixed(
    df,
    initial_equity,
    risk_fraction,
    stop_pct,
    rr,
    min_score,
    cooldown_bars,
):
    equity = float(initial_equity)
    peak = equity
    max_dd = 0.0

    trades = []

    # Prevent overlapping positions.
    next_trade_index = 0

    for i in range(len(df) - 1):

        if i < next_trade_index:
            continue

        # IMPORTANT:
        # generate_signal() now returns 5 values because
        # absorption information was added.
        signal_data = generate_signal(
            df.iloc[i],
            min_score=min_score,
        )
        signal = signal_data["direction"]
        score = signal_data["score"]
        reasons = signal_data["reasons"]

        if signal == "FLAT":
            continue

        entry = float(
            df.iloc[i + 1]["open"]
        )

        stop_distance = entry * stop_pct
        tp_distance = stop_distance * rr

        side = (
            1
            if signal == "LONG"
            else -1
        )

        stop = entry - side * stop_distance
        target = entry + side * tp_distance

        qty = _risk_position(
            entry,
            stop_distance,
            equity,
            risk_fraction,
        )

        exit_price = None
        exit_index = len(df) - 1

        outcome = "TIME"
        exit_reason = "end_of_test"

        max_favorable_r = 0.0
        max_adverse_r = 0.0

        for j in range(i + 1, len(df)):

            bar = df.iloc[j]

            high = float(bar["high"])
            low = float(bar["low"])

            max_favorable_r, max_adverse_r = _update_excursions(
                entry,
                side,
                stop_distance,
                high,
                low,
                max_favorable_r,
                max_adverse_r,
            )

            hit_stop = (
                low <= stop
                if side == 1
                else high >= stop
            )

            hit_target = (
                high >= target
                if side == 1
                else low <= target
            )

            # Stop first when both are touched
            # inside the same candle.
            if hit_stop:
                (
                    exit_price,
                    outcome,
                    exit_reason,
                    exit_index,
                ) = (
                    stop,
                    "LOSS",
                    "stop_loss",
                    j,
                )
                break

            if hit_target:
                (
                    exit_price,
                    outcome,
                    exit_reason,
                    exit_index,
                ) = (
                    target,
                    "WIN",
                    "take_profit",
                    j,
                )
                break

        if exit_price is None:
            exit_price = float(
                df.iloc[-1]["close"]
            )

        pnl = (
            (exit_price - entry)
            * qty
            * side
        )

        equity += pnl

        peak = max(peak, equity)

        dd = (
            (peak - equity) / peak * 100
            if peak
            else 0.0
        )

        max_dd = max(
            max_dd,
            dd,
        )

        trades.append(
            _base_trade(
                df,
                i,
                exit_index,
                signal,
                score,
                reasons,
                entry,
                exit_price,
                pnl,
                outcome,
                rr,
                max_dd,
                stop_distance,
                max_favorable_r,
                max_adverse_r,
                exit_reason,
                stop_distance * qty,
                extra={
                    "target_price": target,
                    "target_r": rr,
                },
            )
        )

        # One position at a time.
        next_trade_index = (
            exit_index
            + cooldown_bars
            + 1
        )

    result = _stats(
        initial_equity,
        equity,
        trades,
    )

    result["rr"] = rr
    result["max_drawdown_pct"] = max_dd

    return result


def _find_structure_target(
    df: pd.DataFrame,
    entry: float,
    side: int,
    signal_index: int,
    lookback: int = 48,
):
    start = max(
        0,
        signal_index - lookback,
    )

    history = df.iloc[
        start:signal_index + 1
    ]

    if len(history) < 5:
        return None

    highs = history["high"]
    lows = history["low"]

    candidates = []

    for k in range(
        2,
        len(history) - 2,
    ):

        h = float(
            highs.iloc[k]
        )

        l = float(
            lows.iloc[k]
        )

        if h >= float(
            highs.iloc[k - 2:k + 3].max()
        ):
            if side == 1 and h > entry:
                candidates.append(h)

        if l <= float(
            lows.iloc[k - 2:k + 3].min()
        ):
            if side == -1 and l < entry:
                candidates.append(l)

    if not candidates:

        if side == 1:
            above = history["high"][
                history["high"] > entry
            ]

            return (
                float(above.iloc[-1])
                if not above.empty
                else None
            )

        below = history["low"][
            history["low"] < entry
        ]

        return (
            float(below.iloc[-1])
            if not below.empty
            else None
        )

    return (
        min(candidates)
        if side == 1
        else max(candidates)
    )


def _single_structure(
    df,
    initial_equity,
    risk_fraction,
    stop_pct,
    min_score,
    cooldown_bars,
):
    equity = float(initial_equity)
    peak = equity
    max_dd = 0.0

    trades = []

    # Prevent overlapping positions.
    next_trade_index = 0

    for i in range(len(df) - 1):

        if i < next_trade_index:
            continue

        signal_data = generate_signal(
            df.iloc[i],
            min_score=min_score,
        )
        signal = signal_data["direction"]
        score = signal_data["score"]
        reasons = signal_data["reasons"]

        if signal == "FLAT":
            continue

        entry = float(
            df.iloc[i + 1]["open"]
        )

        stop_distance = entry * stop_pct

        side = (
            1
            if signal == "LONG"
            else -1
        )

        initial_stop = (
            entry
            - side * stop_distance
        )

        qty = _risk_position(
            entry,
            stop_distance,
            equity,
            risk_fraction,
        )

        structure_target = _find_structure_target(
            df,
            entry,
            side,
            i,
            lookback=48,
        )

        if structure_target is None:
            structure_target = (
                entry
                + side * stop_distance
            )

        target_r = (
            abs(structure_target - entry)
            / stop_distance
        )

        target_r = max(
            0.5,
            target_r,
        )

        target = (
            entry
            + side
            * (
                stop_distance
                * target_r
            )
        )

        current_stop = initial_stop

        partial_done = False

        remaining_qty = qty

        realized_pnl = 0.0

        exit_price = None
        exit_index = len(df) - 1

        outcome = "TIME"
        exit_reason = "end_of_test"

        max_favorable_r = 0.0
        max_adverse_r = 0.0

        trail_active = False
        be_triggered = False
        trailing_activated = False

        for j in range(i + 1, len(df)):

            bar = df.iloc[j]

            high = float(bar["high"])
            low = float(bar["low"])

            max_favorable_r, max_adverse_r = _update_excursions(
                entry,
                side,
                stop_distance,
                high,
                low,
                max_favorable_r,
                max_adverse_r,
            )

            # Move to BE after +1R.
            if max_favorable_r >= 1.0:

                if side == 1:
                    current_stop = max(
                        current_stop,
                        entry,
                    )
                else:
                    current_stop = min(
                        current_stop,
                        entry,
                    )

                trail_active = True
                be_triggered = True

            # Three-bar structure trail.
            if trail_active and j >= 3:

                if side == 1:

                    trail = float(
                        df.iloc[j - 3:j]["low"].min()
                    )

                    current_stop = max(
                        current_stop,
                        trail,
                    )

                else:

                    trail = float(
                        df.iloc[j - 3:j]["high"].max()
                    )

                    current_stop = min(
                        current_stop,
                        trail,
                    )

                trailing_activated = True

            hit_stop = (
                low <= current_stop
                if side == 1
                else high >= current_stop
            )

            hit_target = (
                high >= target
                if side == 1
                else low <= target
            )

            if hit_stop:

                exit_price = current_stop

                remaining_pnl = (
                    (exit_price - entry)
                    * remaining_qty
                    * side
                )

                realized_pnl += remaining_pnl

                exit_index = j

                outcome = (
                    "PARTIAL+TRAIL"
                    if partial_done
                    else "LOSS"
                )

                exit_reason = (
                    "trailing_stop"
                    if trail_active
                    else "stop_loss"
                )

                break

            if hit_target and not partial_done:

                partial_qty = qty * 0.50

                partial_pnl = (
                    (target - entry)
                    * partial_qty
                    * side
                )

                realized_pnl += partial_pnl

                remaining_qty = (
                    qty - partial_qty
                )

                partial_done = True

                outcome = "PARTIAL"

                trail_active = True
                trailing_activated = True

                current_stop = target

        if exit_price is None:

            exit_price = float(
                df.iloc[-1]["close"]
            )

            pnl = (
                (exit_price - entry)
                * remaining_qty
                * side
            )

            realized_pnl += pnl

            exit_index = len(df) - 1

            outcome = (
                "PARTIAL+TIME"
                if partial_done
                else "TIME"
            )

        equity += realized_pnl

        peak = max(
            peak,
            equity,
        )

        dd = (
            (peak - equity)
            / peak
            * 100
            if peak
            else 0.0
        )

        max_dd = max(
            max_dd,
            dd,
        )

        trades.append(
            _base_trade(
                df,
                i,
                exit_index,
                signal,
                score,
                reasons,
                entry,
                exit_price,
                realized_pnl,
                outcome,
                "dynamic_structure",
                max_dd,
                stop_distance,
                max_favorable_r,
                max_adverse_r,
                exit_reason,
                stop_distance * qty,
                extra={
                    "target_price": target,
                    "target_r": target_r,
                    "partial_taken": partial_done,
                    "partial_size_pct": 50.0,
                    "be_triggered": be_triggered,
                    "trailing_activated": trailing_activated,
                    "structure_target": structure_target,
                },
            )
        )

        # One position at a time.
        next_trade_index = (
            exit_index
            + cooldown_bars
            + 1
        )

    result = _stats(
        initial_equity,
        equity,
        trades,
        extra={
            "rr": "dynamic_structure",
            "partial_size_pct": 50.0,
            "target_min_r": 0.5,
            "trailing_activation_r": 1.0,
            "structure_lookback_bars": 48,
        },
    )

    result["max_drawdown_pct"] = max_dd

    return result