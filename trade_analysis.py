"""V3 diagnostic analysis for RR2 trade logs.

Diagnostic only: no parameter optimization and no strategy changes.

V3 adds:
- direction-normalized delta/CVD/flow features
- early MFE/MAE snapshots at 5/10/15 minutes when excursion paths are present
- a strict fallback: no fake early data is reconstructed from final MFE/MAE
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

MFE_BINS = [-float("inf"), 0.5, 1.0, 1.5, 2.0, float("inf")]
MFE_LABELS = ["<0.5R", "0.5–1R", "1–1.5R", "1.5–2R", ">=2R"]
SCORE_BINS = [-float("inf"), 3.5, 4.0, 4.5, float("inf")]
SCORE_LABELS = ["<3.5", "3.5–<4.0", "4.0–<4.5", ">=4.5"]


def group_analysis(df, group_col):
    rows = []
    for key, g in df.groupby(group_col, dropna=False, observed=False):
        wins = (g["outcome"] == "WIN").sum()
        gp = g.loc[g["rr_realized"] > 0, "rr_realized"].sum()
        gl = -g.loc[g["rr_realized"] < 0, "rr_realized"].sum()
        rows.append({
            group_col: key,
            "trades": len(g),
            "wins": wins,
            "losses": (g["outcome"] == "LOSS").sum(),
            "timeouts": (g["outcome"] == "TIME").sum(),
            "win_rate": wins / len(g) if len(g) else 0,
            "expectancy_R": g["rr_realized"].mean(),
            "profit_factor": gp / gl if gl else float("inf"),
            "avg_mfe_R": g["mfe_r"].mean(),
            "median_mfe_R": g["mfe_r"].median(),
            "avg_mae_R": g["mae_r"].mean(),
            "median_mae_R": g["mae_r"].median(),
            "avg_score_abs": g["score"].abs().mean(),
        })
    return pd.DataFrame(rows)


def parse_bool(series):
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def add_directional_features(df):
    out = df.copy()
    direction = out["direction"].astype(str).str.upper()
    sign = pd.Series(0.0, index=out.index)
    sign.loc[direction.eq("LONG")] = 1.0
    sign.loc[direction.eq("SHORT")] = -1.0

    # Positive means flow aligned with the trade direction.
    out["directional_delta_z"] = out["delta_z"] * sign
    out["directional_cvd_slope_z"] = out["cvd_slope_z"] * sign

    ratio = out["buy_sell_ratio"].where(out["buy_sell_ratio"] > 0)
    out["directional_flow"] = ratio.map(lambda x: math.log(x) if pd.notna(x) else float("nan")) * sign

    out["flow_alignment"] = "UNKNOWN"
    out.loc[out["directional_delta_z"] > 0, "flow_alignment"] = "FAVORABLE"
    out.loc[out["directional_delta_z"] < 0, "flow_alignment"] = "ADVERSE"
    out.loc[out["directional_delta_z"] == 0, "flow_alignment"] = "NEUTRAL"
    return out


def parse_path_cell(value):
    if pd.isna(value):
        return []
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [float(x) for x in parsed]
    except Exception:
        pass
    sep = ";" if ";" in text else ","
    try:
        return [float(x.strip()) for x in text.split(sep) if x.strip()]
    except Exception:
        return []


def add_early_excursions(df):
    out = df.copy()
    path_candidates = ["excursion_path_r", "mfe_path_r", "mae_path_r", "intratrade_path_r", "path_r"]
    path_col = next((c for c in path_candidates if c in out.columns), None)

    for minute in (5, 10, 15):
        out[f"mfe_{minute}m_r"] = pd.NA
        out[f"mae_{minute}m_r"] = pd.NA

    if path_col is None:
        return out, None

    bar_minutes = pd.to_numeric(out.get("bar_minutes", pd.Series(5.0, index=out.index)), errors="coerce").fillna(5.0)

    for idx, value in out[path_col].items():
        path = parse_path_cell(value)
        if not path:
            continue
        for minute in (5, 10, 15):
            steps = max(1, int(round(minute / float(bar_minutes.loc[idx]))))
            prefix = path[:steps]
            if prefix:
                out.loc[idx, f"mfe_{minute}m_r"] = max(0.0, max(prefix))
                out.loc[idx, f"mae_{minute}m_r"] = min(0.0, min(prefix))

    return out, path_col


def feature_diagnostic(df, mask, label):
    a = df.loc[mask]
    b = df.loc[~mask]
    features = [
        "score", "volume_z", "delta_z", "cvd_slope_z", "buy_sell_ratio",
        "directional_delta_z", "directional_cvd_slope_z", "directional_flow",
        "duration_minutes", "mfe_r", "mae_r",
    ]
    rows = []
    for col in features:
        rows.append({
            "feature": col,
            "group": label,
            "n": len(a),
            "mean": a[col].mean(),
            "median": a[col].median(),
            "other_mean": b[col].mean(),
            "other_median": b[col].median(),
            "mean_difference": a[col].mean() - b[col].mean(),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="RR2 trade diagnostic V3")
    parser.add_argument("--input", default=None)
    parser.add_argument("--output-dir", default="results/trade_analysis_rr2")
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
    elif Path("data/trades_2_0.csv").exists():
        input_path = Path("data/trades_2_0.csv")
    else:
        input_path = Path("trades_2_0.csv")

    if not input_path.exists():
        raise SystemExit("Input CSV not found. Put trades_2_0.csv in the repository root or data/ or pass --input <path>.")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(input_path)

    required = {
        "timestamp", "direction", "score", "outcome", "duration_minutes",
        "mfe_r", "mae_r", "rr_realized", "rr_model", "exit_reason",
        "volume_z", "delta_z", "cvd_slope_z", "cvd_condition",
        "delta_condition", "buy_sell_ratio", "big_trade", "vwap", "distance_to_poc",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"Missing columns: {', '.join(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    numeric_cols = [
        "score", "duration_minutes", "mfe_r", "mae_r", "rr_realized",
        "volume_z", "delta_z", "cvd_slope_z", "buy_sell_ratio",
        "distance_to_poc", "vwap",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["big_trade_bool"] = parse_bool(df["big_trade"])
    df = add_directional_features(df)
    df, path_col = add_early_excursions(df)

    if "distance_to_vwap" in df.columns:
        df["price_vs_vwap"] = pd.to_numeric(df["distance_to_vwap"], errors="coerce")
    elif "entry" in df.columns:
        df["price_vs_vwap"] = pd.to_numeric(df["entry"], errors="coerce") - df["vwap"]
    else:
        df["price_vs_vwap"] = pd.NA

    df["vwap_relation"] = "UNKNOWN"
    df.loc[df["price_vs_vwap"] > 0, "vwap_relation"] = "ABOVE"
    df.loc[df["price_vs_vwap"] < 0, "vwap_relation"] = "BELOW"
    df.loc[df["price_vs_vwap"] == 0, "vwap_relation"] = "AT_VWAP"

    df["cvd_direction"] = "NEUTRAL"
    df.loc[df["cvd_slope_z"] > 0, "cvd_direction"] = "UP"
    df.loc[df["cvd_slope_z"] < 0, "cvd_direction"] = "DOWN"
    df["delta_direction"] = "NEUTRAL"
    df.loc[df["delta_z"] > 0, "delta_direction"] = "BUY"
    df.loc[df["delta_z"] < 0, "delta_direction"] = "SELL"

    df["mfe_bucket"] = pd.cut(df["mfe_r"], bins=MFE_BINS, labels=MFE_LABELS, right=False)
    df["score_bucket"] = pd.cut(df["score"].abs(), bins=SCORE_BINS, labels=SCORE_LABELS, right=False)
    df["hour_utc"] = df["timestamp"].dt.hour
    df["hour_block_utc"] = ((df["hour_utc"] // 4 * 4).astype("Int64").map(
        lambda x: f"{int(x):02d}-{int(x) + 4:02d}" if pd.notna(x) else "UNKNOWN"
    ))

    low_mfe_loss = (df["outcome"] == "LOSS") & (df["mfe_r"] < 0.5)
    mid_mfe_loss = (df["outcome"] == "LOSS") & (df["mfe_r"] >= 0.5) & (df["mfe_r"] < 2.0)
    high_mfe_loss = (df["outcome"] == "LOSS") & (df["mfe_r"] >= 1.0)
    full_potential = df["mfe_r"] >= 2.0

    n = len(df)
    wins = (df["outcome"] == "WIN").sum()
    gross_profit = df.loc[df["rr_realized"] > 0, "rr_realized"].sum()
    gross_loss = -df.loc[df["rr_realized"] < 0, "rr_realized"].sum()

    summary = pd.DataFrame({
        "metric": [
            "trades", "wins", "losses", "timeouts", "win_rate", "expectancy_R",
            "profit_factor", "avg_mfe_R", "median_mfe_R", "avg_mae_R",
            "median_mae_R", "avg_duration_min", "avg_score_abs", "max_drawdown_R",
        ],
        "value": [
            n, wins, (df["outcome"] == "LOSS").sum(), (df["outcome"] == "TIME").sum(),
            wins / n if n else 0, df["rr_realized"].mean() if n else 0,
            gross_profit / gross_loss if gross_loss else float("inf"),
            df["mfe_r"].mean() if n else 0, df["mfe_r"].median() if n else 0,
            df["mae_r"].mean() if n else 0, df["mae_r"].median() if n else 0,
            df["duration_minutes"].mean() if n else 0, df["score"].abs().mean() if n else 0,
            df["drawdown"].max() if "drawdown" in df else float("nan"),
        ],
    })
    summary.to_csv(out / "summary.csv", index=False)

    analyses = {
        "mfe_buckets.csv": group_analysis(df, "mfe_bucket"),
        "score_buckets.csv": group_analysis(df, "score_bucket"),
        "direction.csv": group_analysis(df, "direction"),
        "cvd_condition.csv": group_analysis(df, "cvd_direction"),
        "delta_condition.csv": group_analysis(df, "delta_direction"),
        "vwap.csv": group_analysis(df, "vwap_relation"),
        "big_trade.csv": group_analysis(df, "big_trade_bool"),
        "hour_blocks_utc.csv": group_analysis(df, "hour_block_utc"),
        "outcome.csv": group_analysis(df, "outcome"),
        "exit_reason.csv": group_analysis(df, "exit_reason"),
        "flow_alignment.csv": group_analysis(df, "flow_alignment"),
    }
    for filename, table in analyses.items():
        table.to_csv(out / filename, index=False)

    quality_rows = []
    for label, mask in [
        ("LOSS_MFE_<0.5R", low_mfe_loss),
        ("LOSS_MFE_0.5R_to_<2R", mid_mfe_loss),
        ("LOSS_MFE_>=1R", high_mfe_loss),
        ("MFE_>=2R", full_potential),
    ]:
        subset = df.loc[mask]
        quality_rows.append({
            "population": label,
            "trades": len(subset),
            "wins": (subset["outcome"] == "WIN").sum(),
            "losses": (subset["outcome"] == "LOSS").sum(),
            "win_rate": (subset["outcome"] == "WIN").mean() if len(subset) else 0,
            "expectancy_R": subset["rr_realized"].mean() if len(subset) else 0,
            "avg_mfe_R": subset["mfe_r"].mean() if len(subset) else 0,
            "median_mfe_R": subset["mfe_r"].median() if len(subset) else 0,
            "avg_mae_R": subset["mae_r"].mean() if len(subset) else 0,
            "avg_duration_min": subset["duration_minutes"].mean() if len(subset) else 0,
            "avg_score_abs": subset["score"].abs().mean() if len(subset) else 0,
        })
    pd.DataFrame(quality_rows).to_csv(out / "trade_quality_populations.csv", index=False)

    feature_tables = []
    for label, mask in [
        ("LOSS_MFE_<0.5R", low_mfe_loss),
        ("LOSS_MFE_>=1R", high_mfe_loss),
        ("MFE_>=2R", full_potential),
    ]:
        feature_tables.append(feature_diagnostic(df, mask, label))
    pd.concat(feature_tables, ignore_index=True).to_csv(out / "feature_diagnostics.csv", index=False)

    directional_rows = []
    for label, mask in [
        ("LOSS_MFE_<0.5R", low_mfe_loss),
        ("LOSS_MFE_0.5R_to_<2R", mid_mfe_loss),
        ("MFE_>=2R", full_potential),
    ]:
        a, b = df.loc[mask], df.loc[~mask]
        for col in ["directional_delta_z", "directional_cvd_slope_z", "directional_flow"]:
            directional_rows.append({
                "feature": col,
                "group": label,
                "n": len(a),
                "mean": a[col].mean(),
                "median": a[col].median(),
                "other_mean": b[col].mean(),
                "other_median": b[col].median(),
                "mean_difference": a[col].mean() - b[col].mean(),
            })
    pd.DataFrame(directional_rows).to_csv(out / "directional_diagnostics.csv", index=False)

    df["directional_delta_bucket"] = pd.cut(
        df["directional_delta_z"],
        bins=[-float("inf"), -1.0, -0.5, 0.0, 0.5, 1.0, float("inf")],
        labels=["<-1", "-1--0.5", "-0.5-0", "0-0.5", "0.5-1", ">1"],
        right=False,
    )
    df["directional_cvd_bucket"] = pd.cut(
        df["directional_cvd_slope_z"],
        bins=[-float("inf"), -0.5, 0.0, 0.5, float("inf")],
        labels=["<-0.5", "-0.5-0", "0-0.5", ">0.5"],
        right=False,
    )
    bucket_tables = []
    for col in ["directional_delta_bucket", "directional_cvd_bucket", "flow_alignment"]:
        t = group_analysis(df, col)
        t.insert(0, "condition", col)
        bucket_tables.append(t)
    pd.concat(bucket_tables, ignore_index=True).to_csv(out / "directional_flow_conditions.csv", index=False)

    early_rows = []
    for minute in (5, 10, 15):
        mfe_col, mae_col = f"mfe_{minute}m_r", f"mae_{minute}m_r"
        valid = df[mfe_col].notna() & df[mae_col].notna()
        for label, mask in [("LOSS_MFE_<0.5R", low_mfe_loss), ("MFE_>=2R", full_potential)]:
            a, b = df.loc[mask & valid], df.loc[(~mask) & valid]
            early_rows.append({
                "minute": minute,
                "population": label,
                "n": len(a),
                "avg_mfe_R": a[mfe_col].mean() if len(a) else float("nan"),
                "median_mfe_R": a[mfe_col].median() if len(a) else float("nan"),
                "avg_mae_R": a[mae_col].mean() if len(a) else float("nan"),
                "median_mae_R": a[mae_col].median() if len(a) else float("nan"),
                "other_avg_mfe_R": b[mfe_col].mean() if len(b) else float("nan"),
                "other_avg_mae_R": b[mae_col].mean() if len(b) else float("nan"),
            })
    pd.DataFrame(early_rows).to_csv(out / "early_excursion_diagnostics.csv", index=False)

    condition_cols = [
        "direction", "cvd_direction", "delta_direction", "vwap_relation",
        "score_bucket", "hour_block_utc", "big_trade_bool", "flow_alignment",
        "directional_delta_bucket", "directional_cvd_bucket",
    ]
    rows = []
    for col in condition_cols:
        for value, g in df.groupby(col, dropna=False, observed=False):
            rows.append({
                "condition": col, "value": value, "trades": len(g),
                "wins": (g["outcome"] == "WIN").sum(),
                "losses": (g["outcome"] == "LOSS").sum(),
                "win_rate": (g["outcome"] == "WIN").mean(),
                "expectancy_R": g["rr_realized"].mean(),
                "avg_mfe_R": g["mfe_r"].mean(), "avg_mae_R": g["mae_r"].mean(),
            })
    pd.DataFrame(rows).to_csv(out / "entry_conditions.csv", index=False)

    df.loc[low_mfe_loss].sort_values("mfe_r").to_csv(out / "losses_mfe_lt_0_5R.csv", index=False)
    df.loc[high_mfe_loss].sort_values("mfe_r", ascending=False).to_csv(out / "losses_with_mfe_ge_1R.csv", index=False)

    df[df["outcome"] == "LOSS"].groupby("mfe_bucket", observed=False).agg(
        trades=("mfe_r", "size"),
        avg_mfe_R=("mfe_r", "mean"),
        median_mfe_R=("mfe_r", "median"),
        avg_mae_R=("mae_r", "mean"),
        avg_score_abs=("score", lambda s: s.abs().mean()),
        avg_duration_min=("duration_minutes", "mean"),
    ).reset_index().to_csv(out / "loss_mfe_diagnostic.csv", index=False)

    early_available = path_col is not None and df["mfe_5m_r"].notna().any()
    report = f"""# RR2 Trade Diagnostic V3

Input: {input_path}
Trades: {n}
Wins: {wins}
Losses: {(df["outcome"] == "LOSS").sum()}
Timeouts: {(df["outcome"] == "TIME").sum()}
Win rate: {(wins / n * 100):.2f}%
Expectancy: {df["rr_realized"].mean():.4f}R
Profit factor: {(gross_profit / gross_loss if gross_loss else float("inf")):.4f}

## V3 diagnostics

- Direction-normalized delta/CVD/flow features: added.
- Positive directional flow means flow aligned with the trade direction.
- Early 5/10/15 minute MFE/MAE: {"available from an intratrade path column." if early_available else "NOT available from this CSV; final MFE/MAE are not used as a fake early proxy."}
- No thresholds, sessions, targets, or strategy rules were optimized.

## Generated files

- directional_diagnostics.csv
- directional_flow_conditions.csv
- flow_alignment.csv
- early_excursion_diagnostics.csv
- feature_diagnostics.csv
- trade_quality_populations.csv

This report is descriptive only. It does not optimize parameters or modify the strategy.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    print(f"Analysis V3 complete: {out.resolve()}")
    print(f"Main report: {(out / 'REPORT.md').resolve()}")


if __name__ == "__main__":
    main()