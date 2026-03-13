# =============================================================================
# Trade Ideas Dashboard — Configuration
# =============================================================================

# ---------------------------------------------------------------------------
# Assets: key → (display_name, yfinance_ticker, COT_code | None)
# ---------------------------------------------------------------------------
ASSETS = {
    "gold":   {"name": "XAU/USD", "ticker": "GC=F",      "cot_code": "088691", "currency": "USD", "pip": 0.1},
    "btc":    {"name": "BTC/USD", "ticker": "BTC-USD",    "cot_code": None,     "currency": "USD", "pip": 1.0},
    "oil":    {"name": "WTI Oil", "ticker": "CL=F",       "cot_code": "067651", "currency": "USD", "pip": 0.01},
    "eurusd": {"name": "EUR/USD", "ticker": "EURUSD=X",   "cot_code": "099741", "currency": "USD", "pip": 0.0001},
    "gbpusd": {"name": "GBP/USD", "ticker": "GBPUSD=X",   "cot_code": "096742", "currency": "USD", "pip": 0.0001},
    "usdjpy": {"name": "USD/JPY", "ticker": "JPY=X",      "cot_code": "097741", "currency": "JPY", "pip": 0.01,  "invert": True},
    "audusd": {"name": "AUD/USD", "ticker": "AUDUSD=X",   "cot_code": "232741", "currency": "USD", "pip": 0.0001},
}

# ---------------------------------------------------------------------------
# CFTC COT Report URL
# ---------------------------------------------------------------------------
COT_REPORT_URL_TEMPLATE = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
COT_HISTORICAL_YEARS = 2       # years to download for 52W percentile

# ---------------------------------------------------------------------------
# Data history
# ---------------------------------------------------------------------------
WEEKLY_HISTORY_YEARS  = 2      # weekly OHLCV for Weinstein (30W MA needs ~35 bars min)
DAILY_HISTORY_DAYS    = 365    # calendar days of daily OHLCV
INTRADAY_4H_DAYS      = 60     # calendar days of 4H data

# ---------------------------------------------------------------------------
# Stan Weinstein Stage Analysis
# ---------------------------------------------------------------------------
WEINSTEIN_MA_LONG    = 30      # primary 30-week SMA
WEINSTEIN_MA_SHORT   = 10      # 10-week SMA for slope direction
WEINSTEIN_VOL_MULT   = 1.5     # volume > this × 10W avg = expansion
WEINSTEIN_SLOPE_FLAT = 0.002   # abs(slope/MA) < this → flat

# ---------------------------------------------------------------------------
# Larry Williams COT Commercial Index
# ---------------------------------------------------------------------------
COT_COMMERCIAL_BULLISH = 75    # commercial index > this → smart money net long
COT_COMMERCIAL_BEARISH = 25    # commercial index < this → smart money net short
COT_WINDOW             = 52    # weeks for min/max percentile

# Williams %R
WILLIAMS_R_PERIOD     = 14
WILLIAMS_R_OVERSOLD   = -80    # below this = oversold → potential long entry
WILLIAMS_R_OVERBOUGHT = -20    # above this = overbought → potential short entry

# ---------------------------------------------------------------------------
# ICT Engine (4H timeframe)
# ---------------------------------------------------------------------------
ICT_SWING_ORDER          = 3     # bars each side for fractal swing detection
ICT_FVG_LOOKBACK         = 30    # candles to scan for FVGs
ICT_OB_LOOKBACK          = 30    # candles to scan for OBs
ICT_OB_MIN_IMPULSE_PCT   = 0.003 # 0.3% move qualifies as impulse after OB
ICT_OTE_LOW              = 0.618 # OTE zone lower (golden ratio)
ICT_OTE_HIGH             = 0.705 # OTE zone upper (ICT-specific)
ICT_FIB_LEVELS           = [0.236, 0.382, 0.5, 0.618, 0.705, 0.786]
ICT_ATR_PERIOD           = 14

# ---------------------------------------------------------------------------
# Session / Killzone times (EST = UTC-5)
# ---------------------------------------------------------------------------
# Format: (start_hour_utc, start_min_utc, end_hour_utc, end_min_utc, label)
KILLZONES = [
    (7,  0, 10,  0, "London Killzone"),    # 02:00–05:00 EST = 07:00–10:00 UTC
    (12, 0, 15,  0, "NY Open Killzone"),   # 07:00–10:00 EST = 12:00–15:00 UTC
    (15, 0, 17,  0, "London Close"),       # 10:00–12:00 EST = 15:00–17:00 UTC
]

# ---------------------------------------------------------------------------
# Mark Douglas Grading — confluence point system
# ---------------------------------------------------------------------------
CONFLUENCE_POINTS = {
    "weinstein_stage":   2,    # Weinstein stage aligned with direction
    "cot_commercial":    2,    # COT commercial signal aligned
    "williams_r":        1,    # Williams %R in entry zone
    "ict_ote":           1,    # Price in ICT OTE zone (0.618–0.705)
    "order_block":       1,    # 4H order block present at entry
    "fvg":               1,    # 4H Fair Value Gap at entry
    "killzone":          1,    # Active killzone session
    "daily_bias":        1,    # Daily bias aligned (PDH/PDL swept)
}

GRADE_THRESHOLDS = {
    "A+": 7,     # >= 7 points
    "A":  5,     # 5–6 points
    "B":  3,     # 3–4 points
    # C (<3) is filtered out and not displayed
}
GRADE_MIN_DISPLAY = 3   # minimum points to display a trade idea

# Grade colours for UI
GRADE_COLORS = {
    "A+": "#00C853",
    "A":  "#69F0AE",
    "B":  "#FFD740",
    "C":  "#FF6D00",
}

# ---------------------------------------------------------------------------
# Weinstein stage badge colours
# ---------------------------------------------------------------------------
STAGE_COLORS = {
    1: "#FFD740",   # Basing — yellow
    2: "#00C853",   # Advancing — green
    3: "#FFD740",   # Topping — yellow
    4: "#D50000",   # Declining — red
}

STAGE_LABELS = {
    1: "S1 Basing",
    2: "S2 Advancing",
    3: "S3 Topping",
    4: "S4 Declining",
}

# ---------------------------------------------------------------------------
# Risk / position sizing defaults
# ---------------------------------------------------------------------------
DEFAULT_ACCOUNT_SIZE  = 10_000   # USD
DEFAULT_RISK_PCT      = 1.0      # % per trade
DEFAULT_RR_TARGET1    = 2.0      # minimum risk:reward for Target 1
DEFAULT_RR_TARGET2    = 4.0      # stretch Target 2

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
PAGE_TITLE        = "Trade Ideas Dashboard"
REFRESH_TTL_SECS  = 3600        # Streamlit cache TTL
