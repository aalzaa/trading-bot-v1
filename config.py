import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    symbol: str = os.getenv("SYMBOL", "BTCUSDT")
    market: str = os.getenv("MARKET", "um")
    bar_minutes: int = int(os.getenv("BAR_MINUTES", "5"))
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.005"))
    stop_pct: float = float(os.getenv("STOP_PCT", "0.0025"))
    take_profit_rr: float = float(os.getenv("TAKE_PROFIT_RR", "0.75"))
    min_signal_score: float = float(os.getenv("MIN_SIGNAL_SCORE", "3.0"))
    volume_z_min: float = float(os.getenv("VOLUME_Z_MIN", "1.0"))
    delta_z_min: float = float(os.getenv("DELTA_Z_MIN", "1.0"))
    cvd_slope_z_min: float = float(os.getenv("CVD_SLOPE_Z_MIN", "0.5"))
    big_trade_percentile: float = float(os.getenv("BIG_TRADE_PERCENTILE", "0.99"))
    cooldown_bars: int = int(os.getenv("COOLDOWN_BARS", "2"))
    max_positions: int = int(os.getenv("MAX_POSITIONS", "1"))
    live_trading: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"


CONFIG = Config()
