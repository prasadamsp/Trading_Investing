# =============================================================================
# Bitcoin Weekly Bias Dashboard — Configuration
# =============================================================================

# ---------------------------------------------------------------------------
# Yahoo Finance tickers
# ---------------------------------------------------------------------------
TICKERS = {
    # Bitcoin & Crypto
    "btc":    "BTC-USD",      # Bitcoin spot price
    "eth":    "ETH-USD",      # Ethereum spot price (BTC dominance proxy)

    # USD
    "dxy":    "DX-Y.NYB",     # US Dollar Index

    # Rates
    "tnx":    "^TNX",         # 10Y Treasury yield
    "irx":    "^IRX",         # 13-week T-Bill
    "tyx":    "^TYX",         # 30Y Treasury yield
    "tlt":    "TLT",          # iShares 20Y Bond ETF (rate expectations)

    # Equities / Risk
    "spx":    "^GSPC",        # S&P 500
    "vix":    "^VIX",         # CBOE VIX
    "qqq":    "QQQ",          # Nasdaq ETF (BTC tracks tech more than broad market)

    # FX
    "eurusd": "EURUSD=X",     # Euro vs USD
    "usdjpy": "JPY=X",        # USD vs JPY

    # Commodities
    "gold":   "GC=F",         # Gold futures (BTC vs Gold ratio)

    # Bitcoin Spot ETFs (for flow tracking)
    "ibit":   "IBIT",         # BlackRock iShares Bitcoin Trust
    "fbtc":   "FBTC",         # Fidelity Wise Origin Bitcoin Fund
    "gbtc":   "GBTC",         # Grayscale Bitcoin Trust
    "arkb":   "ARKB",         # ARK 21Shares Bitcoin ETF
    "hodl":   "HODL",         # VanEck Bitcoin ETF
    "bitb":   "BITB",         # Bitwise Bitcoin ETF
}

# ---------------------------------------------------------------------------
# FRED series IDs (requires free API key)
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "real_yield_10y":    "DFII10",      # 10Y TIPS real yield
    "breakeven_10y":     "T10YIE",      # 10Y Breakeven Inflation
    "fed_funds":         "FEDFUNDS",    # Effective Fed Funds Rate
    "cpi_yoy":           "CPIAUCSL",    # CPI All Urban Consumers
    "pce_yoy":           "PCEPI",       # PCE Price Index
    "treasury_2y":       "DGS2",        # 2Y Treasury Yield (daily)
    "treasury_10y":      "DGS10",       # 10Y Treasury Yield (daily)
    "m2":                "M2SL",        # M2 Money Supply (BTC is a monetary asset)
}

# ---------------------------------------------------------------------------
# CFTC COT — Bitcoin futures contract code (CME)
# ---------------------------------------------------------------------------
COT_BTC_CODE = "133741"
COT_REPORT_URL_TEMPLATE = (
    "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
)
COT_HISTORICAL_YEARS = 2   # years of COT history to download for percentile calc

# ---------------------------------------------------------------------------
# Fear & Greed API (alternative.me — no API key required)
# ---------------------------------------------------------------------------
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=365&format=json"

# ---------------------------------------------------------------------------
# Indicator parameters
# ---------------------------------------------------------------------------
WEEKLY_MA_PERIODS = [20, 50, 200]   # weeks
RSI_PERIOD = 14                      # weeks
MACD_FAST = 12                       # weeks
MACD_SLOW = 26                       # weeks
MACD_SIGNAL = 9                      # weeks
COT_PERCENTILE_WINDOW = 52           # weeks for COT index percentile
FEAR_GREED_PERCENTILE_WINDOW = 52    # weeks for F&G percentile

# ---------------------------------------------------------------------------
# Scoring weights (must sum to 1.0)
# ---------------------------------------------------------------------------
# BTC is a risk-on asset — sentiment and macro drive it more than gold
SCORING_WEIGHTS = {
    "macro":       0.30,
    "sentiment":   0.35,
    "technical":   0.25,
    "cross_asset": 0.10,
}

# Sentiment sub-weights
# BTC sentiment is heavily driven by Fear & Greed and ETF inflows
SENTIMENT_SUB_WEIGHTS = {
    "fear_greed":  0.35,   # Crypto Fear & Greed Index (contrarian)
    "etf_flows":   0.35,   # BTC spot ETF net flows
    "cot_index":   0.20,   # CME BTC futures COT percentile (contrarian)
    "btc_eth":     0.10,   # BTC/ETH ratio trend (BTC dominance proxy)
}

# Technical sub-weights (same as gold)
TECHNICAL_SUB_WEIGHTS = {
    "ma_20w":    0.15,
    "ma_50w":    0.25,
    "ma_200w":   0.30,
    "rsi":       0.15,
    "macd":      0.15,
}

# Cross-asset sub-weights
# BTC is risk-on: SPX positive, VIX negative (opposite of gold)
CROSS_ASSET_SUB_WEIGHTS = {
    "vix":     0.30,   # rising VIX = risk-off = bearish BTC
    "spx":     0.30,   # rising SPX = risk-on = bullish BTC
    "eurusd":  0.20,   # rising EUR/USD = weak USD = bullish BTC
    "gold":    0.10,   # BTC/Gold ratio trend
    "qqq":     0.10,   # Nasdaq as high-beta risk proxy
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
# Data history (for charts and calculations)
# ---------------------------------------------------------------------------
PRICE_HISTORY_YEARS = 5    # years of weekly price data to fetch

# ---------------------------------------------------------------------------
# ICT Analysis parameters
# ---------------------------------------------------------------------------
ICT_MONTHLY_YEARS     = 10    # years of monthly OHLCV to fetch
ICT_DAILY_DAYS        = 90    # calendar days of daily OHLCV to fetch
ICT_SWING_ORDER       = 4     # bars each side to confirm a swing point (fractal)
ICT_FVG_LOOKBACK      = 20    # candles back to scan for Fair Value Gaps
ICT_OB_LOOKBACK       = 20    # candles back to scan for Order Blocks
ICT_OB_MIN_IMPULSE    = 0.5   # % move that qualifies as an impulse after an OB
ICT_FIB_LEVELS        = [0.236, 0.382, 0.5, 0.618, 0.705, 0.786]
ICT_OTE_LOW           = 0.618  # Optimal Trade Entry zone lower bound (golden ratio)
ICT_OTE_HIGH          = 0.705  # Optimal Trade Entry zone upper bound (ICT-specific)
ICT_PREMIUM_THRESHOLD = 0.5   # above this fib level = premium, below = discount

# ---------------------------------------------------------------------------
# ICT Trade Generation — tunable thresholds
# ---------------------------------------------------------------------------
ICT_DAILY_SWING_LOOKBACK      = 30      # primary lookback bars for _find_major_swing()
ICT_DAILY_SWING_FALLBACK      = 60      # fallback bars if primary range < min_range
ICT_DAILY_SWING_MIN_RANGE_PCT = 0.01    # min swing range as fraction of current price
ICT_BIAS_BULL_THRESHOLD       = 0.05    # bias_score > this  → bullish overall_bias
ICT_BIAS_BEAR_THRESHOLD       = -0.05   # bias_score < this  → bearish overall_bias
ICT_CONFIDENCE_HIGH_THRESHOLD = 0.30    # abs(bias_score) > this → "HIGH" confidence
ICT_OB_NEAR_LONG_UPPER        = 1.05    # bullish OB filter: ob.high ≤ price × this (wider for BTC volatility)
ICT_OB_NEAR_LONG_LOWER        = 0.85    # bullish OB filter: ob.high ≥ price × this (wider for BTC volatility)
ICT_OB_NEAR_SHORT_LOWER       = 0.95    # bearish OB filter: ob.low  ≥ price × this
ICT_OB_NEAR_SHORT_UPPER       = 1.15    # bearish OB filter: ob.low  ≤ price × this
ICT_OB_STOP_BUFFER_FRACTION   = 0.50    # stop buffer = ob_range × this
ICT_OB_STOP_BUFFER_FALLBACK   = 0.005   # fallback stop buffer = price × this (higher for BTC)
ICT_LIQ_STOP_PCT              = 0.010   # Trade 3 stop distance (wider for BTC volatility)
ICT_ATR_PERIOD                = 14      # ATR period for dynamic stop sizing
ICT_OTE_ATR_MULTIPLIER        = 1.5     # Trade 2 stop buffer = ATR × this
ICT_LIQ_ATR_MULTIPLIER        = 1.0     # Trade 3 stop buffer = ATR × this
ICT_OTE_STOP_FALLBACK_PCT     = 0.010   # Trade 2 fallback stop buffer (wider for BTC)
ICT_LIQ_STOP_FALLBACK_PCT     = 0.008   # Trade 3 fallback stop buffer (wider for BTC)

# ---------------------------------------------------------------------------
# BTC Halving Cycle — known dates + cycle parameters
# ---------------------------------------------------------------------------
BTC_HALVING_DATES = [
    "2012-11-28",   # Halving 1: reward 25 BTC/block
    "2016-07-09",   # Halving 2: reward 12.5 BTC/block
    "2020-05-11",   # Halving 3: reward 6.25 BTC/block
    "2024-04-19",   # Halving 4: reward 3.125 BTC/block
    "2028-04-17",   # Halving 5: reward 1.5625 BTC/block (estimated)
]
BTC_CYCLE_LENGTH_DAYS = 1458            # historical avg days between halvings

# Phase thresholds (months after last halving)
BTC_HALVING_EARLY_BULL_MONTHS = 18      # 0-18m  → Early Bull (supply shock builds) → bullish
BTC_HALVING_PEAK_MONTHS       = 30      # 18-30m → Peak Risk Zone → bearish
BTC_HALVING_BEAR_MONTHS       = 42      # 30-42m → Bear Market → bearish
# 42m+                                  # Pre-Halving accumulation → bullish

# ---------------------------------------------------------------------------
# On-Chain Data — blockchain.com charts API (no API key required)
# ---------------------------------------------------------------------------
BLOCKCHAIN_API_BASE = "https://api.blockchain.info/charts"
BLOCKCHAIN_TIMESPAN = "2years"          # timespan param for blockchain.com API

# ---------------------------------------------------------------------------
# CoinGecko free API (no key needed for global market data)
# ---------------------------------------------------------------------------
COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"

# ---------------------------------------------------------------------------
# OKX public API — funding rate + open interest (no key, globally accessible)
# ---------------------------------------------------------------------------
OKX_FUNDING_URL     = "https://www.okx.com/api/v5/public/funding-rate-history"
OKX_OI_URL          = "https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume"
OKX_INSTRUMENT      = "BTC-USDT-SWAP"
OKX_FUNDING_LIMIT   = 200           # records (~66 days at 8h intervals)
OKX_OI_PERIOD       = "1D"
OKX_OI_LIMIT        = 30           # 30 daily OI bars

# Funding rate signal thresholds (as % per 8h period)
FUNDING_EXTREME_LONG    = 0.05         # > 0.05% → very crowded longs → bearish signal
FUNDING_MILD_LONG       = 0.01         # 0.01–0.05% → mild long bias → neutral
FUNDING_EXTREME_SHORT   = -0.01        # < -0.01% → shorts crowded → contrarian bullish

# ---------------------------------------------------------------------------
# Bollinger Bands parameters (weekly)
# ---------------------------------------------------------------------------
BB_PERIOD   = 20    # 20-week BB (same as 20W MA already tracked)
BB_STD_MULT = 2.0   # standard deviation multiplier

# ---------------------------------------------------------------------------
# Psychological price levels to monitor
# ---------------------------------------------------------------------------
BTC_PSYCH_LEVELS = [
    10_000, 20_000, 30_000, 40_000, 50_000,
    60_000, 70_000, 75_000, 80_000, 90_000,
    100_000, 110_000, 120_000, 150_000, 200_000,
]

# ---------------------------------------------------------------------------
# Updated MACRO_SUB_WEIGHTS — includes BTC-specific halving + hashrate signals
# (reduced dxy and real_yield slightly to accommodate new BTC fundamentals)
# ---------------------------------------------------------------------------
MACRO_SUB_WEIGHTS = {
    "dxy":          0.25,   # USD direction (key macro driver)
    "real_yield":   0.15,   # Real interest rate
    "fed_funds":    0.15,   # Rate cycle
    "breakeven":    0.10,   # Inflation expectations
    "cpi":          0.10,   # CPI trend
    "pce":          0.05,   # PCE trend
    "yield_curve":  0.05,   # 10Y-2Y spread direction
    "halving":      0.10,   # BTC halving cycle phase (unique to BTC)
    "hashrate":     0.05,   # Network hash rate trend (miner confidence)
}

# Sentiment sub-weights v2 — added funding_rate signal (perpetual market sentiment)
# Reduced fear_greed and etf_flows by 5% each to accommodate new derivative signal
SENTIMENT_SUB_WEIGHTS_V2 = {
    "fear_greed":    0.30,   # Crypto Fear & Greed Index (contrarian)
    "etf_flows":     0.30,   # BTC spot ETF net flows
    "cot_index":     0.20,   # CME BTC futures COT percentile (contrarian)
    "btc_eth":       0.10,   # BTC/ETH ratio trend (BTC dominance proxy)
    "funding_rate":  0.10,   # Perp funding rate (extreme longs = bearish, shorts = bullish)
}
