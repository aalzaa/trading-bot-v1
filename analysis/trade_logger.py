from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


FEATURE_COLUMNS = (
    "volume_z",
    "delta_z",
    "cvd_slope_z",
    "buy_sell_ratio",
    "big_trade",
    "vwap",
    "distance_to_poc",
)


def _jsonable(value):
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"), default=str)
    return value


def write_trade_logs(results: dict, output_dir: str = "results") -> None:
    """
    Write one compact CSV per exit model.

    The backtest already keeps only completed trades in memory; this function
    serializes them after each model without retaining duplicate DataFrames.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for model, result in results.items():
        trades = result.get("trade_log", [])
        if not trades:
            pd.DataFrame().to_csv(out / f"trades_{_safe_name(model)}.csv", index=False)
            continue

        frame = pd.DataFrame(trades)
        if "reasons" in frame.columns:
            frame["reasons"] = frame["reasons"].map(_jsonable)

        frame.to_csv(out / f"trades_{_safe_name(model)}.csv", index=False)


def write_summary(results: dict, output_dir: str = "results") -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary = {}
    for model, result in results.items():
        summary[model] = {
            key: value
            for key, value in result.items()
            if key != "trade_log"
        }

    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )


def _safe_name(name) -> str:
    return str(name).replace(".", "_").replace("/", "_").replace(" ", "_")
