# =============================================================================
# Oil Weekly Bias Dashboard — Scoring Engine
# =============================================================================
"""
Each scorer returns -1 (bearish), 0 (neutral), or +1 (bullish) for WTI crude oil.
score_all() computes the weighted aggregate score and maps it to a bias label.

Key oil-specific inversions vs gold:
- Rising CPI = BULLISH oil (oil IS inflation)
- Rising SPX = BULLISH oil (demand/growth signal)
- Rising VIX = BEARISH oil (demand destruction risk)
- EIA inventory DRAW = BULLISH; BUILD = BEARISH
- Rising rig count = BEARISH (more future supply)
- Wide Brent-WTI spread = BULLISH (geopolitical premium)
"""
import config


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sign_score(val, bullish_if_positive: bool = True) -> int:
    """Simple sign-based score with a small neutral band."""
    if val is None:
        return 0
    if bullish_if_positive:
        return 1 if val > 0 else (-1 if val < 0 else 0)
    else:
        return 1 if val < 0 else (-1 if val > 0 else 0)


# ---------------------------------------------------------------------------
# Macro scorers
# ---------------------------------------------------------------------------

def score_dxy(macro: dict) -> int:
    """Falling DXY → bullish oil (oil priced in USD; weaker dollar = higher oil)."""
    chg = macro.get("dxy", {}).get("weekly_chg")
    return _sign_score(chg, bullish_if_positive=False)


def score_real_yield(macro: dict) -> int:
    """Rising real yields dampen demand / investment → bearish oil."""
    delta = macro.get("real_yield_10y", {}).get("delta")
    if delta is None:
        return 0
    if delta < -0.05:
        return 1     # real yields falling = demand-friendly
    if delta > 0.05:
        return -1    # real yields rising = demand dampener
    return 0


def score_fed_funds(macro: dict) -> int:
    """Fed cutting cycle → growth bullish → demand bullish for oil."""
    delta = macro.get("fed_funds", {}).get("delta")
    return _sign_score(delta, bullish_if_positive=False)


def score_cpi(macro: dict) -> int:
    """High CPI → bullish oil (oil drives/reflects inflation; high CPI = supply driven)."""
    yoy = macro.get("cpi_yoy", {}).get("value")
    if yoy is None:
        return 0
    if yoy > 3.0:
        return 1    # elevated inflation = oil reflecting tight supply
    if yoy < 2.0:
        return -1   # low inflation = weak demand environment
    return 0


def score_pce(macro: dict) -> int:
    """PCE inflation above 2.5% → bullish oil (similar to CPI)."""
    yoy = macro.get("pce_yoy", {}).get("value")
    if yoy is None:
        return 0
    if yoy > 2.5:
        return 1
    if yoy < 1.5:
        return -1
    return 0


def score_yield_curve(macro: dict) -> int:
    """
    Inverted yield curve = recession risk → demand destruction → bearish oil.
    Steepening from deep inversion = recovery signal → mildly bullish.
    """
    val = macro.get("yield_curve", {}).get("value")
    steepening = macro.get("yield_curve", {}).get("steepening")
    if val is None:
        return 0
    if val < -0.30:
        return -1 if not steepening else 0   # deep inversion = recession risk
    if val > 0.50:
        return 1 if steepening else 0         # healthy curve steepening = growth
    return 0


# ---------------------------------------------------------------------------
# Supply/Demand scorers
# ---------------------------------------------------------------------------

def score_eia_crude(supply: dict) -> int:
    """EIA crude inventory draw (negative change) → bullish; build → bearish."""
    draw = supply.get("eia", {}).get("crude_draw_mbbl")
    if draw is None:
        return 0
    if draw <= config.EIA_CRUDE_DRAW_BULLISH:
        return 1    # significant draw
    if draw >= config.EIA_CRUDE_BUILD_BEARISH:
        return -1   # significant build
    return 0


def score_eia_gasoline(supply: dict) -> int:
    """EIA gasoline inventory draw → bullish demand signal."""
    draw = supply.get("eia", {}).get("gasoline_draw_mbbl")
    if draw is None:
        return 0
    if draw <= config.EIA_GAS_DRAW_BULLISH:
        return 1
    if draw >= config.EIA_GAS_BUILD_BEARISH:
        return -1
    return 0


def score_rig_count(supply: dict) -> int:
    """
    Rising US rig count → more future supply → bearish (lagged effect ~6 months).
    Falling rig count → supply tightening → bullish.
    """
    chg = supply.get("rig_count", {}).get("weekly_chg")
    if chg is None:
        return 0
    if chg <= config.RIG_COUNT_FALLING_THRESHOLD:
        return 1    # rigs declining = supply tightening
    if chg >= config.RIG_COUNT_RISING_THRESHOLD:
        return -1   # rigs rising = supply expanding
    return 0


def score_seasonal(supply: dict) -> int:
    """Seasonal demand model score (already normalised to [-1, +1] in config)."""
    raw = supply.get("seasonal", {}).get("score")
    if raw is None:
        return 0
    if raw > 0.2:
        return 1
    if raw < -0.2:
        return -1
    return 0


def score_imports(supply: dict) -> int:
    """
    Rising US crude imports YoY = more supply arriving = mildly bearish.
    Falling imports YoY = tighter supply = mildly bullish.
    Monthly data — use as trend signal only.
    """
    imp = supply.get("imports", {})
    rising = imp.get("rising")
    if rising is None:
        return 0
    return -1 if rising else 1


def score_brent_wti(supply: dict) -> int:
    """
    Wide Brent-WTI spread (Brent > WTI) = geopolitical risk premium → bullish.
    WTI > Brent (negative spread) = US supply glut or pipeline bottleneck → bearish.
    """
    spread = supply.get("brent_wti", {}).get("spread")
    if spread is None:
        return 0
    if spread >= config.BRENT_WTI_GEOPOLITICAL_PREMIUM:
        return 1    # geopolitical risk premium priced in
    if spread <= config.BRENT_WTI_CONTANGO_SIGNAL:
        return -1   # US supply pressure
    return 0


# ---------------------------------------------------------------------------
# Sentiment scorers
# ---------------------------------------------------------------------------

def score_cot_index(sentiment: dict) -> int:
    """Contrarian: extreme spec longs (>80th pct) = bearish; extreme shorts (<20th) = bullish."""
    cot_idx = sentiment.get("cot", {}).get("cot_index")
    if cot_idx is None:
        return 0
    if cot_idx < 20:
        return 1
    if cot_idx > 80:
        return -1
    return 0


def score_cot_trend(sentiment: dict) -> int:
    """Trend-following: net speculative long rising → bullish."""
    cot_df = sentiment.get("cot_df")
    if cot_df is None or cot_df.empty or "noncomm_net" not in cot_df.columns:
        return 0
    net = cot_df["noncomm_net"].dropna()
    if len(net) < 2:
        return 0
    delta = float(net.iloc[-1]) - float(net.iloc[-2])
    return _sign_score(delta, bullish_if_positive=True)


def score_etf_flows(sentiment: dict) -> int:
    """Net positive ETF flows across XLE + XOP + USO → bullish oil."""
    avg = sentiment.get("etf", {}).get("combined_flow_avg_pct")
    if avg is None:
        return 0
    if avg > config.ETF_FLOW_BULLISH_THRESHOLD:
        return 1
    if avg < config.ETF_FLOW_BEARISH_THRESHOLD:
        return -1
    return 0


# ---------------------------------------------------------------------------
# Technical scorers
# ---------------------------------------------------------------------------

def score_ma(technical: dict, period: int) -> int:
    """Price above MA → bullish; below → bearish."""
    ma_data = technical.get("moving_averages", {}).get(period)
    if ma_data is None:
        return 0
    return 1 if ma_data["above"] else -1


def score_rsi(technical: dict) -> int:
    """RSI: 50-70 = bullish momentum; >75 = overbought; <35 = bearish."""
    rsi = technical.get("rsi")
    if rsi is None:
        return 0
    if 50 <= rsi <= 70:
        return 1
    if rsi > 75:
        return -1   # overbought
    if rsi < 35:
        return -1   # weak
    return 0


def score_macd(technical: dict) -> int:
    """MACD histogram above zero or fresh bullish cross → bullish."""
    macd = technical.get("macd", {})
    bullish    = macd.get("bullish")
    crossing_up = macd.get("crossing_up")
    if bullish is None:
        return 0
    if crossing_up:
        return 1
    if bullish:
        return 1
    return -1


def score_ovx(technical: dict) -> int:
    """
    OVX rising sharply → uncertainty; very high OVX can signal panic selloff =
    contrarian bullish (supply shock reversal). Normal OVX direction: falling = bullish.
    """
    ovx = technical.get("ovx", {})
    val = ovx.get("value")
    chg = ovx.get("weekly_chg")
    very_high = ovx.get("very_high_vol", False)

    if val is None:
        return 0
    if very_high and chg and chg < -5:
        return 1    # OVX collapsing from extreme = panic subsiding = bullish
    if chg and chg > 15:
        return -1   # OVX spiking sharply = demand shock / risk-off
    if chg and chg < -5 and not very_high:
        return 1    # OVX falling = confidence returning
    return 0


# ---------------------------------------------------------------------------
# Master scoring
# ---------------------------------------------------------------------------

def score_all(indicators: dict) -> dict:
    """
    Returns {score, label, color, breakdown, group_scores}.
    Score range: -1.0 (Strong Bearish) to +1.0 (Strong Bullish).
    """
    macro    = indicators.get("macro", {})
    supply   = indicators.get("supply", {})
    tech     = indicators.get("technical", {})
    sent     = indicators.get("sentiment", {})

    # ── Macro scores ──
    macro_scores = {
        "dxy":         score_dxy(macro),
        "real_yield":  score_real_yield(macro),
        "fed_funds":   score_fed_funds(macro),
        "cpi":         score_cpi(macro),
        "pce":         score_pce(macro),
        "yield_curve": score_yield_curve(macro),
    }
    macro_group = sum(
        macro_scores[k] * config.MACRO_SUB_WEIGHTS.get(k, 0)
        for k in macro_scores
    )

    # ── Supply/Demand scores ──
    supply_scores = {
        "eia_crude":    score_eia_crude(supply),
        "eia_gasoline": score_eia_gasoline(supply),
        "rig_count":    score_rig_count(supply),
        "seasonal":     score_seasonal(supply),
        "brent_wti":    score_brent_wti(supply),
        "imports":      score_imports(supply),
    }
    supply_group = sum(
        supply_scores[k] * config.SUPPLY_SUB_WEIGHTS.get(k, 0)
        for k in supply_scores
    )

    # ── Sentiment scores ──
    sentiment_scores = {
        "cot_index":  score_cot_index(sent),
        "cot_trend":  score_cot_trend(sent),
        "etf_flows":  score_etf_flows(sent),
    }
    sentiment_group = sum(
        sentiment_scores[k] * config.SENTIMENT_SUB_WEIGHTS.get(k, 0)
        for k in sentiment_scores
    )

    # ── Technical scores ──
    technical_scores = {
        "ma_20w":  score_ma(tech, 20),
        "ma_50w":  score_ma(tech, 50),
        "ma_200w": score_ma(tech, 200),
        "rsi":     score_rsi(tech),
        "macd":    score_macd(tech),
        "ovx":     score_ovx(tech),
    }
    technical_group = sum(
        technical_scores[k] * config.TECHNICAL_SUB_WEIGHTS.get(k, 0)
        for k in {k: v for k, v in technical_scores.items() if k in config.TECHNICAL_SUB_WEIGHTS}
    )
    # OVX is a bonus signal: not in sub-weights, added as 0.10 weight
    technical_group += technical_scores["ovx"] * 0.10
    # Re-normalise technical to [-1, 1] since we added extra weight
    sub_total = sum(config.TECHNICAL_SUB_WEIGHTS.values()) + 0.10
    technical_group = technical_group / sub_total if sub_total > 0 else technical_group

    # ── Weighted aggregate ──
    w = config.SCORING_WEIGHTS
    aggregate = (
        macro_group     * w["macro"] +
        supply_group    * w["supply"] +
        sentiment_group * w["sentiment"] +
        technical_group * w["technical"]
    )
    aggregate = round(max(-1.0, min(1.0, aggregate)), 4)

    # ── Map to label ──
    label, color = "NEUTRAL", "#FFD740"
    for lo, hi, lbl, clr in config.BIAS_LEVELS:
        if lo <= aggregate <= hi:
            label, color = lbl, clr
            break

    return {
        "score":   aggregate,
        "label":   label,
        "color":   color,
        "breakdown": {
            "macro":     macro_scores,
            "supply":    supply_scores,
            "sentiment": sentiment_scores,
            "technical": technical_scores,
        },
        "group_scores": {
            "macro":     round(macro_group,     4),
            "supply":    round(supply_group,    4),
            "sentiment": round(sentiment_group, 4),
            "technical": round(technical_group, 4),
        },
    }
