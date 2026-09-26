# Trading Bot V1 — Data-Driven Order Flow

Research/backtesting bot for BTCUSDT USD-M Futures using Binance public historical aggTrades.

## Repository layout

```
trading-bot-v1/
├── analysis/                 # Trade log serialization
│   └── trade_logger.py
├── backtest/                 # Backtest engine
│   └── orderflow_engine.py
├── data/                     # Data loaders and research input
│   ├── binance_data.py
│   └── trades_2_0.csv
├── features/                 # Feature engineering
│   └── orderflow.py
├── news/                     # Optional news filter
│   ├── calendar.csv
│   └── news_filter.py
├── strategy/                 # Signal generation
│   └── signal.py
├── research/                 # Saved diagnostic reports
│   └── RR2_REPORT.md
├── results/                  # Generated locally; ignored by Git
├── trade_analysis.py         # RR2 diagnostic entry point
├── main.py                   # Main backtest entry point
├── config.py                 # Configuration
├── requirements.txt
└── .env.example
```

## RR2 diagnostic

The historical trade log is stored at `data/trades_2_0.csv`.

Run from the repository root:

```powershell
python trade_analysis.py
```

Generated diagnostics go to:

```
results/trade_analysis_rr2/
```

Or specify paths manually:

```powershell
python trade_analysis.py --input data/trades_2_0.csv --output-dir results/trade_analysis_rr2
```

V3 adds direction-normalized delta/CVD/flow diagnostics and only calculates early 5/10/15 minute excursions when a real intratrade path is present.

## Running the backtest

Example:

```powershell
python main.py backtest --start 2026-03-01 --end 2026-03-08
```

The default bar interval is 5 minutes. It can be changed with:

```powershell
python main.py backtest --start 2026-03-01 --end 2026-03-08 --bar-minutes 5
```

Backtest output is written to `results/`.

## Research workflow

1. Diagnose the existing signal.
2. Form a hypothesis from the diagnostics.
3. Make the smallest possible strategy change.
4. Test on an independent validation period.
5. Test again on a fully out-of-sample period.
6. Only then consider paper/live execution.

Do not optimize thresholds on the same sample used to discover them.

## Official reference configuration (26/09/2026)

**`asia-london`** is the official reference configuration for current research.

Base strategy:
- CVD
- Delta
- CVD multi-bar slope
- Strong-entry filtering
- Volume Profile / POC
- Big Trade
- Absorption

Session filter:
- New entries only during **Asia + London: 00:00–12:59 UTC**
- Existing positions are not force-closed when the session window ends.

The previous `cvd-delta-strong-entry` configuration remains as historical baseline material and comparison reference, but is no longer the official project baseline.

## Current V1 scope

- Binance USD-M Futures BTCUSDT aggTrades.
- Aggressive buy/sell volume and delta from `is_buyer_maker`.
- CVD, relative volume and delta/CVD Z-scores.
- Aggressive buy/sell ratio.
- Rolling volume-profile POC approximation.
- Session VWAP as confluence.
- Big-trade proxy based on rolling trade-size percentile.
- Fixed-RR research models from 0.5R to 2R.
- Experimental structure/trailing model.
- `LIVE_TRADING=false`; no live execution path in V1.

## Important limitations

- Historical aggTrades provide executed trades, not historical full order-book depth.
- Open Interest, liquidations, options flow and GEX are not fabricated in V1.
- The Volume Profile POC is an approximation.
- Fees and slippage are not yet included in the historical results.
- A positive backtest is not proof of a live edge.
