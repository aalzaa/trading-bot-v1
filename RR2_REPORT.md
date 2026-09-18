# RR2 Trade Diagnostic V3

Input: data/trades_2_0.csv
Trades: 180
Wins: 62
Losses: 117
Timeouts: 1
Win rate: 34.44%
Expectancy: 0.0393R
Profit factor: 1.0604

## V3 diagnostics

- Direction-normalized delta/CVD/flow features: added.
- Positive directional flow means flow aligned with the trade direction.
- Early 5/10/15 minute MFE/MAE: NOT available from this CSV; final MFE/MAE are not used as a fake early proxy.
- No thresholds, sessions, targets, or strategy rules were optimized.

## Key interpretation

The sample is close to breakeven before fees/slippage. The diagnostic showed that low-MFE losses had substantially worse MAE than trades reaching 2R, while raw volume did not strongly separate the populations. Direction-normalized flow is the next diagnostic dimension, but this one-week sample is not sufficient to establish a robust edge.

This report is descriptive only. It does not optimize parameters or modify the strategy.
