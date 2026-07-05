"""Central configuration and constants for Techna.

No indicator math lives here — only paths, the canonical data schema, and
plain defaults. Keeping these in one place means every module reads and
writes data in exactly the same shape.
"""
from __future__ import annotations

from pathlib import Path

# Project root = parent of the `techna` package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Shared on-disk cache for fetched price data (the "fetch once, reuse" store).
CACHE_DIR = PROJECT_ROOT / "data_cache"

# Where generated markdown reports are written.
REPORTS_DIR = PROJECT_ROOT / "reports"

# Canonical OHLCV schema that every module relies on, in this exact order.
OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
PRICE_COLUMNS = ["Open", "High", "Low", "Close"]

# Defaults for data requests.
# "2y" comfortably covers SMA200 warm-up (200 bars) plus enough trailing
# history for a 50/200 cross to plausibly appear, not just the bare minimum.
DEFAULT_INTERVAL = "1d"
DEFAULT_PERIOD = "2y"

# Cached data whose LAST BAR is more than this many calendar days old is
# considered stale: the real network path auto-refreshes it (falling back to
# the stale cache, with a warning, if the fetch fails). 1 day means an
# automated daily run fetches at most once per day instead of freezing on the
# first day's data forever. Injected fetchers (tests/fixtures) are exempt.
CACHE_STALE_DAYS = 1

# State-classification thresholds (kept here, not in indicators/, so they can
# be tuned without touching the pure indicator math).
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
RSI_PERIOD = 14

# --- Trend (daily + weekly MTF) --------------------------------------------- #
SMA_FAST = 20
SMA_MID = 50
SMA_SLOW = 200
WEEKLY_SMA_FAST = 10
WEEKLY_SMA_SLOW = 40

# --- MACD -------------------------------------------------------------------- #
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- Bollinger Bands --------------------------------------------------------- #
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0

# --- Context & regime layer (Phase 6) -------------------------------------- #
# All Wilder-smoothed. Kept here so the indicator math stays pure/parametric.
ATR_PERIOD = 14
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25.0       # ADX >= this => trending; below => ranging
VOL_REGIME_LOOKBACK = 100        # bars used to rank the current ATR% percentile
VOL_REGIME_HIGH_PCT = 0.80       # ATR% at/above this percentile => "high" vol
VOL_REGIME_LOW_PCT = 0.20        # ATR% at/below this percentile => "low" vol
SWING_WINDOW = 5                 # k for swing-point (pivot) detection
DIVERGENCE_LOOKBACK = 60         # bars to search for the two most recent swings

# --- Levels Significance Filter (Phase 7) --------------------------------- #
LEVEL_CLUSTER_PCT = 0.01          # cluster tolerance = last_price * LEVEL_CLUSTER_PCT
LEVEL_TOP_N = 5                  # return at most top N support/resistance levels

# --- Empirical Base Rates (Phase 8) --------------------------------------- #
BASE_RATE_HORIZONS = [5, 10, 20]
BASE_RATE_MIN_SAMPLE = 20

# --- Relative Strength vs Benchmark (Phase 9) ------------------------------ #
RS_MA_WINDOW = 50
DEFAULT_BENCHMARK = "SPY"

# --- Volume Analysis (Phase 11) ------------------------------------------- #
VWAP_DEFAULT_PERIOD = 20
OBV_DIVERGENCE_LOOKBACK = 20

# --- Econometric Analysis (Phase 12) --------------------------------------- #
ACF_LAGS = 40
ACF_EARLY_LAGS = 5
ACF_MIN_SIGNIFICANT = 2
ECON_MIN_RETURNS = 30

# --- Risk Context Analysis (Phases 13-16) ---------------------------------- #
WEEK52_WINDOW = 252
WEEK52_HIGH_PCT = 90.0
WEEK52_LOW_PCT = 10.0

LIQ_HIGH_VALUE = 50_000_000
LIQ_LOW_VALUE = 5_000_000

BETA_HIGH = 1.3
BETA_LOW = 0.7

# --- Stationarity and Structural Breaks (Phases 19-20) --------------------- #
STATIONARITY_REG_LEVELS = "ct"
STATIONARITY_REG_RETURNS = "c"
BREAK_MIN_SEG = 20
BREAK_MAX = 3
BREAK_MIN_STRENGTH = 15.0
BREAK_VAR_RATIO = 1.5
BREAK_MEAN_STD_DEV = 0.5

# --- Hurst Exponent Analysis (Phase 21) ----------------------------------- #
HURST_MIN_SCALE = 8
HURST_PERSIST = 0.55
HURST_MEANREV = 0.45

# --- Quantile Beta Regression (Phase 22) ----------------------------------- #
QBETA_QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]
QBETA_ASYM_THRESHOLD = 0.25

# --- Regime-Conditional Stats (Phase 23) ----------------------------------- #
REGIME_MIN_OBS = 60

# --- Statistical Rigor Package (Phase 24) ---------------------------------- #
LJUNGBOX_LAGS = 10
VR_Q_VALUES = [2, 4, 8, 16]
BOOT_N = 1000
BOOT_SEED = 42
TAIL_MIN_OBS = 750

# --- Volume Profile (Phase 30) --------------------------------------------- #
VP_LOOKBACK = 252
VP_BINS = 30
VP_VALUE_AREA = 0.70
VP_WEEKLY_LOOKBACK_WEEKS = 104

# --- Volatility Squeeze (Phase 31) ------------------------------------------ #
# Period intentionally reuses BOLLINGER_WINDOW (see call site in techna.py) --
# no separate KC_PERIOD constant, so the two can never silently diverge.
KC_MULT = 1.5

# --- Stochastic Oscillator (Phase 33) --------------------------------------- #
STOCH_K = 14
STOCH_SMOOTH = 3
STOCH_D = 3
STOCH_OVERBOUGHT = 80
STOCH_OVERSOLD = 20

# --- Fibonacci Retracement (Phase 34) --------------------------------------- #
FIB_LOOKBACK = 252
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIB_TOUCH_ATR_MULT = 0.25

# --- Money Flow Index (Phase 36) --------------------------------------------- #
MFI_PERIOD = 14
MFI_OVERBOUGHT = 80.0
MFI_OVERSOLD = 20.0

# --- Donchian Channels (Phase 35) ------------------------------------------- #
DONCHIAN_FAST = 20
DONCHIAN_SLOW = 55



