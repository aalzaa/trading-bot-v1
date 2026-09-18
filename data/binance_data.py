from __future__ import annotations

import gc
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades"


def _days(start: str, end: str):
    current = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    finish = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    while current < finish:
        yield current
        current += timedelta(days=1)


def _download_day(symbol: str, day: datetime, cache_dir: Path) -> Path:
    stamp = day.strftime("%Y-%m-%d")
    filename = f"{symbol}-aggTrades-{stamp}.zip"
    url = f"{BASE_URL}/{symbol}/{filename}"

    cache_dir.mkdir(parents=True, exist_ok=True)
    local_zip = cache_dir / filename

    if local_zip.exists() and local_zip.stat().st_size > 0:
        print(f"Using cached file: {local_zip}")
        return local_zip

    print(f"Downloading: {url}")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    local_zip.write_bytes(response.content)
    return local_zip


def _find_csv(zf: zipfile.ZipFile) -> str:
    csv_files = [name for name in zf.namelist() if name.lower().endswith(".csv")]
    if not csv_files:
        raise RuntimeError("No CSV file found inside Binance ZIP.")
    return csv_files[0]


def _process_chunk(df: pd.DataFrame) -> pd.DataFrame:
    if "price" in df.columns and "quantity" in df.columns:
        df = df.rename(columns={"transact_time": "timestamp"})
    else:
        if df.shape[1] < 7:
            return pd.DataFrame()
        df = df.iloc[:, :7].copy()
        df.columns = [
            "agg_trade_id", "price", "quantity",
            "first_trade_id", "last_trade_id",
            "timestamp", "is_buyer_maker",
        ]

    required = ["price", "quantity", "timestamp", "is_buyer_maker"]
    if any(c not in df.columns for c in required):
        return pd.DataFrame()

    for col in ["price", "quantity", "timestamp"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["price", "quantity", "timestamp"])
    if df.empty:
        return pd.DataFrame()

    buyer_maker = (
        df["is_buyer_maker"].astype(str).str.strip().str.lower()
        .isin(["true", "1"])
    )

    df["buy_volume"] = np.where(buyer_maker, 0.0, df["quantity"])
    df["sell_volume"] = np.where(buyer_maker, df["quantity"], 0.0)
    df["delta"] = df["buy_volume"] - df["sell_volume"]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    return df[
        ["timestamp", "price", "quantity", "buy_volume", "sell_volume", "delta"]
    ]


def _aggregate_day(
    zip_path: Path,
    minutes: int = 5,
    chunksize: int = 500_000,
) -> pd.DataFrame:
    chunks = []

    with zipfile.ZipFile(zip_path) as zf:
        csv_name = _find_csv(zf)

        with zf.open(csv_name) as fh:
            first_line = fh.readline().decode("utf-8", errors="ignore").strip()

        has_header = (
            "price" in first_line.lower()
            and ("quantity" in first_line.lower() or "qty" in first_line.lower())
        )

        with zf.open(csv_name) as fh:
            reader = pd.read_csv(
                fh,
                chunksize=chunksize,
                header=0 if has_header else None,
                low_memory=True,
            )

            for raw_chunk in reader:
                chunk = _process_chunk(raw_chunk)
                del raw_chunk

                if chunk.empty:
                    continue

                chunk["bar_time"] = chunk["timestamp"].dt.floor(f"{minutes}min")

                grouped = (
                    chunk.groupby("bar_time")
                    .agg(
                        open=("price", "first"),
                        high=("price", "max"),
                        low=("price", "min"),
                        close=("price", "last"),
                        volume=("quantity", "sum"),
                        buy_volume=("buy_volume", "sum"),
                        sell_volume=("sell_volume", "sum"),
                        delta=("delta", "sum"),
                        trade_count=("price", "size"),
                        max_trade_size=("quantity", "max"),
                    )
                )

                chunks.append(grouped)
                del chunk, grouped

    if not chunks:
        return pd.DataFrame()

    result = pd.concat(chunks)

    result = (
        result.groupby(level=0)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            buy_volume=("buy_volume", "sum"),
            sell_volume=("sell_volume", "sum"),
            delta=("delta", "sum"),
            trade_count=("trade_count", "sum"),
            max_trade_size=("max_trade_size", "max"),
        )
        .sort_index()
    )

    return result


def _add_orderflow_columns(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()

    x["cvd"] = x["delta"].cumsum()
    x["buy_sell_ratio"] = (
        x["buy_volume"] / x["sell_volume"].replace(0, np.nan)
    )

    volume_mean = x["volume"].rolling(20, min_periods=5).mean()
    volume_std = x["volume"].rolling(20, min_periods=5).std()
    delta_mean = x["delta"].rolling(20, min_periods=5).mean()
    delta_std = x["delta"].rolling(20, min_periods=5).std()

    x["volume_z"] = (
        (x["volume"] - volume_mean) / volume_std.replace(0, np.nan)
    )
    x["delta_z"] = (
        (x["delta"] - delta_mean) / delta_std.replace(0, np.nan)
    )

    x["cvd_slope"] = x["cvd"] - x["cvd"].shift(5)
    cvd_mean = x["cvd_slope"].rolling(20, min_periods=5).mean()
    cvd_std = x["cvd_slope"].rolling(20, min_periods=5).std()
    x["cvd_slope_z"] = (
        (x["cvd_slope"] - cvd_mean) / cvd_std.replace(0, np.nan)
    )

    threshold = (
        x["max_trade_size"]
        .rolling(100, min_periods=20)
        .quantile(0.95)
    )
    x["big_trade"] = x["max_trade_size"] >= threshold
    x["big_trade_buy"] = x["big_trade"] & (x["delta"] > 0)
    x["big_trade_sell"] = x["big_trade"] & (x["delta"] < 0)

    x["typical_price"] = (x["high"] + x["low"] + x["close"]) / 3.0
    price_bins = x["typical_price"].round(0)
    x["poc"] = x.groupby(price_bins)["volume"].transform("sum")
    x["distance_to_poc"] = x["close"] - x["typical_price"]

    return x.replace([np.inf, -np.inf], np.nan)


def fetch_aggtrades(
    symbol: str,
    start: str,
    end: str,
    cache_dir: str | Path = "data/cache/binance",
    minutes: int = 5,
) -> pd.DataFrame:
    symbol = symbol.upper().replace("/", "")
    cache_dir = Path(cache_dir)

    days = list(_days(start, end))
    daily_bars = []

    print(
        f"Processing {len(days)} day(s) in streaming/chunked mode "
        f"(raw aggTrades are not kept for the whole period)."
    )

    for number, day in enumerate(days, start=1):
        stamp = day.strftime("%Y-%m-%d")
        print(f"[{number}/{len(days)}] Processing {stamp}")

        zip_path = _download_day(symbol, day, cache_dir)
        day_bars = _aggregate_day(
            zip_path,
            minutes=minutes,
            chunksize=500_000,
        )

        if not day_bars.empty:
            daily_bars.append(day_bars)

        del day_bars
        gc.collect()

    if not daily_bars:
        return pd.DataFrame()

    bars = pd.concat(daily_bars).sort_index()
    bars = bars[~bars.index.duplicated(keep="first")]

    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    bars = bars[(bars.index >= start_ts) & (bars.index < end_ts)]

    bars = _add_orderflow_columns(bars)

    print(f"Loaded {len(bars):,} aggregated {minutes}m bars")
    return bars


def aggregate_orderflow(
    trades: pd.DataFrame,
    minutes: int = 5,
    bar_minutes: int | None = None,
) -> pd.DataFrame:
    if bar_minutes is not None:
        minutes = bar_minutes
    return trades.copy()
