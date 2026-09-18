import argparse
import json

from config import CONFIG
from data.binance_data import fetch_aggtrades, aggregate_orderflow
from features.orderflow import add_orderflow_features
from backtest.orderflow_engine import run_backtest
from analysis.trade_logger import write_summary, write_trade_logs


def main():
    parser = argparse.ArgumentParser(description="Trading Bot V1 - data-driven order-flow research")
    sub = parser.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest")
    bt.add_argument("--symbol", default=CONFIG.symbol)
    bt.add_argument("--start", required=True, help="UTC start, e.g. 2026-03-01")
    bt.add_argument("--end", required=True, help="UTC end, e.g. 2026-03-02")
    bt.add_argument("--initial-equity", type=float, default=10_000)
    bt.add_argument("--bar-minutes", type=int, default=CONFIG.bar_minutes)
    bt.add_argument("--output-dir", default="results", help="Directory for trade CSVs and summary JSON")
    args = parser.parse_args()

    if args.command == "backtest":
        trades = fetch_aggtrades(args.symbol, args.start, args.end, minutes=args.bar_minutes)
        if trades.empty:
            raise SystemExit("No Binance aggTrade data returned.")

        bars = aggregate_orderflow(trades, minutes=args.bar_minutes)
        features = add_orderflow_features(bars)
        if features.empty:
            raise SystemExit("Not enough data to build order-flow features. Use a longer test window.")

        results = run_backtest(
            features,
            initial_equity=args.initial_equity,
            risk_fraction=CONFIG.risk_per_trade,
            stop_pct=CONFIG.stop_pct,
            min_score=CONFIG.min_signal_score,
            cooldown_bars=CONFIG.cooldown_bars,
        )

        write_trade_logs(results, args.output_dir)
        write_summary(results, args.output_dir)

        clean = {
            rr: {k: v for k, v in value.items() if k != "trade_log"}
            for rr, value in results.items()
        }
        print(json.dumps(clean, indent=2, default=str))
        print(f"Trade logs written to: {args.output_dir}")


if __name__ == "__main__":
    main()
