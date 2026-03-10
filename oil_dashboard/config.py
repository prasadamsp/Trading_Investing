# =============================================================================
# Oil Weekly Bias Dashboard — Configuration
# =============================================================================

# ---------------------------------------------------------------------------
# Yahoo Finance tickers
# ---------------------------------------------------------------------------
TICKERS = {
    # Oil (primary)
    "wti":       "CL=F",       # WTI Crude Oil futures (continuous)
    "brent":     "BZ=F",       # Brent Crude Oil futures (continuous)

    # Energy products
    "natgas":    "NG=F",       # Natural Gas futures
    "heating":   "HO=F",       # Heating Oil futures
    "gasoline":  "RB=F",       # RBOB Gasoline futures

    # USD
    "dxy":       "DX-Y.NYB",   # US Dollar Index

    # Rates
    "tnx":       "^TNX",       # 10Y Treasury yield
    "irx":       "^IRX",       # 13-week T-Bill
    "tyx":       "^TYX",       # 30Y Treasury yield

    # Equities / Risk
    "spx":       "^GSPC",      # S&P 500
    "vix":       "^VIX",       # CBOE VIX
    "ovx":       "^OVX",       # CBOE Crude Oil Volatility Index

    # Energy ETFs (for flow tracking)
    "xle":       "XLE",        # Energy Select Sector SPDR (large-cap)
    "xop":       "XOP",        # S&P Oil & Gas E&P ETF (small/mid-cap)
    "uso":       "USO",        # United States Oil Fund (WTI futures)

    # FX
    "eurusd":    "EURUSD=X",   # EUR/USD

    # Gold (cross-asset)
    "gold":      "GC=F",       # Gold futures
}

# ---------------------------------------------------------------------------
# FRED series IDs (requires free API key)
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "real_yield_10y":  "DFII10",      # 10Y TIPS real yield
    "breakeven_10y":   "T10YIE",      # 10Y Breakeven Inflation
    "fed_funds":       "FEDFUNDS",    # Effective Fed Funds Rate
    "cpi_yoy":         "CPIAUCSL",    # CPI All Urban Consumers
    "pce_yoy":         "PCEPI",       # PCE Price Index
    "treasury_2y":     "DGS2",        # 2Y Treasury Yield (daily)
    "treasury_10y":    "DGS10",       # 10Y Treasury Yield (daily)
    "rig_count":       "OILRUSA",     # Baker Hughes US Oil Rig Count (weekly)
}

# ---------------------------------------------------------------------------
# EIA Open Data API (requires free API key — https://www.eia.gov/opendata/)
# ---------------------------------------------------------------------------

# ── Weekly petroleum stocks/inventory (draws & builds) ──────────────────
# Route: /petroleum/sum/sndw/ — available at WEEKLY frequency
EIA_STOCKS_URL        = "https://api.eia.gov/v2/petroleum/sum/sndw/data/"
EIA_CRUDE_SERIES      = "W_EPC0_SAX_NUS_MBBL"    # US total crude oil stocks (Mbbl)
EIA_GASOLINE_SERIES   = "W_EPM0_SAX_NUS_MBBL"    # US gasoline stocks (Mbbl)
EIA_DISTILLATE_SERIES = "W_EPLLPZ_SAX_NUS_MBBL"  # US distillate stocks (Mbbl)
EIA_HISTORY_WEEKS     = 104                        # weeks of history to fetch

# ── Crude oil imports (MONTHLY only — EIA limitation) ───────────────────
# Route: /petroleum/move/imp/ — only available at MONTHLY frequency
# Used as a trend signal (YoY direction), not a weekly draw signal
EIA_IMPORTS_URL       = "https://api.eia.gov/v2/petroleum/move/imp/data/"
EIA_IMPORTS_MONTHS    = 24                         # months of import history to fetch

# ---------------------------------------------------------------------------
# CFTC COT — WTI Crude Oil futures contract code (NYMEX)
# ---------------------------------------------------------------------------
COT_OIL_CODE = "067651"
COT_REPORT_URL_TEMPLATE = (
    "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
)
COT_HISTORICAL_YEARS = 2   # years of COT history for percentile calc

# ---------------------------------------------------------------------------
# Indicator parameters
# ---------------------------------------------------------------------------
WEEKLY_MA_PERIODS    = [20, 50, 200]   # weeks
RSI_PERIOD           = 14              # weeks
MACD_FAST            = 12             # weeks
MACD_SLOW            = 26             # weeks
MACD_SIGNAL          = 9             # weeks
COT_PERCENTILE_WINDOW = 52            # weeks for COT index percentile

# Seasonal demand profile (month → score [-1, +1])
# May–Sept: driving season (bullish); Oct–Mar: heating season (moderate);
# April: refinery maintenance start (bearish dip)
SEASONAL_SCORES = {
    1:  0.3,    # Jan  — heating demand peak, cold weather
    2:  0.3,    # Feb  — heating demand
    3:  0.0,    # Mar  — maintenance season begins
    4: -0.3,    # Apr  — spring maintenance peak (bearish dip)
    5:  0.5,    # May  — driving season starts
    6:  0.7,    # Jun  — peak driving season
    7:  0.7,    # Jul  — peak driving season
    8:  0.5,    # Aug  — driving season late stage
    9:  0.0,    # Sep  — driving season ends, maintenance
    10: -0.2,   # Oct  — fall maintenance
    11:  0.3,   # Nov  — heating demand resumes
    12:  0.4,   # Dec  — winter demand
}

# ---------------------------------------------------------------------------
# Scoring weights (must sum to 1.0)
# ---------------------------------------------------------------------------
SCORING_WEIGHTS = {
    "macro":        0.25,   # DXY, rates, inflation environment
    "supply":       0.35,   # EIA inventories, rig count, seasonal — primary for oil
    "sentiment":    0.20,   # COT positioning, ETF flows
    "technical":    0.20,   # MA, RSI, MACD, OVX, Brent-WTI spread
}

# Macro sub-weights (within macro group, must sum to 1.0)
MACRO_SUB_WEIGHTS = {
    "dxy":          0.25,   # USD strength (inverse to oil price)
    "real_yield":   0.15,   # Real rates dampen demand
    "fed_funds":    0.15,   # Rate cycle
    "cpi":          0.25,   # Inflation — oil is inflation; high CPI = bullish oil
    "pce":          0.10,   # PCE inflation
    "yield_curve":  0.10,   # Yield curve (recession risk = bearish demand)
}

# Supply/Demand sub-weights (must sum to 1.0)
SUPPLY_SUB_WEIGHTS = {
    "eia_crude":    0.35,   # Weekly crude inventory draw/build (most important)
    "eia_gasoline": 0.15,   # Gasoline demand proxy
    "rig_count":    0.15,   # Baker Hughes rig count direction (lagged supply signal)
    "seasonal":     0.15,   # Seasonal demand model
    "brent_wti":    0.10,   # Brent-WTI spread (geopolitical risk premium)
    "imports":      0.10,   # Monthly crude imports YoY trend (EIA — monthly only)
}

# Sentiment sub-weights (must sum to 1.0)
SENTIMENT_SUB_WEIGHTS = {
    "cot_index":   0.40,   # COT percentile (contrarian)
    "cot_trend":   0.25,   # COT net direction (trend-following)
    "etf_flows":   0.35,   # XLE + XOP + USO combined flow proxy
}

# Technical sub-weights (must sum to 1.0)
TECHNICAL_SUB_WEIGHTS = {
    "ma_20w":   0.15,
    "ma_50w":   0.25,
    "ma_200w":  0.30,
    "rsi":      0.15,
    "macd":     0.15,
}

# ---------------------------------------------------------------------------
# Bias score thresholds
# ---------------------------------------------------------------------------
BIAS_LEVELS = [
    ( 0.60,  1.00, "STRONG BULLISH", "#00C853"),
    ( 0.20,  0.60, "BULLISH",        "#69F0AE"),
    (-0.20,  0.20, "NEUTRAL",        "#FFD740"),
    (-0.60, -0.20, "BEARISH",        "#FF6D00"),
    (-1.00, -0.60, "STRONG BEARISH", "#D50000"),
]

# ---------------------------------------------------------------------------
# EIA inventory signal thresholds (Thousand Barrels)
# ---------------------------------------------------------------------------
EIA_CRUDE_DRAW_BULLISH   = -1_000   # draw > 1M bbl = bullish
EIA_CRUDE_BUILD_BEARISH  =  1_000   # build > 1M bbl = bearish
EIA_GAS_DRAW_BULLISH     =   -500   # gasoline draw > 500K bbl = bullish
EIA_GAS_BUILD_BEARISH    =    500   # gasoline build > 500K bbl = bearish

# OVX thresholds
OVX_HIGH_VOLATILITY  = 40   # above this = elevated uncertainty
OVX_VERY_HIGH        = 60   # above this = crisis/shock level

# Brent-WTI spread thresholds ($/bbl)
BRENT_WTI_GEOPOLITICAL_PREMIUM = 3.0   # spread > $3 = geopolitical risk premium (bullish)
BRENT_WTI_CONTANGO_SIGNAL      = -1.0  # WTI > Brent = excess US supply (bearish)

# ETF flow signal threshold (weekly % change)
ETF_FLOW_BULLISH_THRESHOLD  =  0.5
ETF_FLOW_BEARISH_THRESHOLD  = -0.5

# Rig count change threshold (weekly)
RIG_COUNT_RISING_THRESHOLD  = 5    # +5 rigs = supply rising (bearish signal)
RIG_COUNT_FALLING_THRESHOLD = -5   # -5 rigs = supply falling (bullish signal)

# ---------------------------------------------------------------------------
# Data history
# ---------------------------------------------------------------------------
PRICE_HISTORY_YEARS = 5    # years of weekly price data to fetch

# ---------------------------------------------------------------------------
# ICT Analysis parameters (same structure as gold, adapted for oil)
# ---------------------------------------------------------------------------
ICT_MONTHLY_YEARS             = 10
ICT_DAILY_DAYS                = 90
ICT_SWING_ORDER               = 3      # oil is more volatile than gold; use 3 bars
ICT_FVG_LOOKBACK              = 20
ICT_OB_LOOKBACK               = 20
ICT_OB_MIN_IMPULSE            = 0.5    # % move qualifying as impulse (higher for oil volatility)
ICT_FIB_LEVELS                = [0.236, 0.382, 0.5, 0.618, 0.705, 0.786]
ICT_OTE_LOW                   = 0.618
ICT_OTE_HIGH                  = 0.705
ICT_PREMIUM_THRESHOLD         = 0.5

ICT_DAILY_SWING_LOOKBACK      = 30
ICT_DAILY_SWING_FALLBACK      = 60
ICT_DAILY_SWING_MIN_RANGE_PCT = 0.02   # 2% min swing range (oil more volatile than gold)
ICT_BIAS_BULL_THRESHOLD       = 0.05
ICT_BIAS_BEAR_THRESHOLD       = -0.05
ICT_CONFIDENCE_HIGH_THRESHOLD = 0.30

# OB proximity filters — wider for oil's higher volatility
ICT_OB_NEAR_LONG_UPPER        = 1.05   # ob.high ≤ price × 1.05
ICT_OB_NEAR_LONG_LOWER        = 0.88   # ob.high ≥ price × 0.88
ICT_OB_NEAR_SHORT_LOWER       = 0.95   # ob.low  ≥ price × 0.95
ICT_OB_NEAR_SHORT_UPPER       = 1.12   # ob.low  ≤ price × 1.12
ICT_OB_STOP_BUFFER_FRACTION   = 0.50
ICT_OB_STOP_BUFFER_FALLBACK   = 0.005  # 0.5% fallback buffer
ICT_LIQ_STOP_PCT              = 0.008  # wider stop for oil
ICT_ATR_PERIOD                = 14
ICT_OTE_ATR_MULTIPLIER        = 1.5
ICT_LIQ_ATR_MULTIPLIER        = 1.0
ICT_OTE_STOP_FALLBACK_PCT     = 0.008
ICT_LIQ_STOP_FALLBACK_PCT     = 0.006
