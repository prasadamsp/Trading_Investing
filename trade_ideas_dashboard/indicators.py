# =============================================================================
# Trade Ideas Dashboard — Indicator Calculations
# =============================================================================
"""
Three indicator families:
  1. Stan Weinstein Stage Analysis (weekly 30-period SMA + slope)
  2. Larry Williams COT Commercial Index (smart money extremes)
  3. Williams %R (entry timing oscillator)
"""
import numpy as np
import pandas as pd

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_last(series: pd.Series, n: int = 1) -> float | None:
    s = series.dropna()
    return float(s.iloc[-n]) if len(s) >= n else None


# ---------------------------------------------------------------------------
# 1. Stan Weinstein Stage Analysis
# ---------------------------------------------------------------------------

def calc_weinstein_stage(weekly_df: pd.DataFrame) -> dict:
    """
    Determine Weinstein stage (1–4) from weekly OHLCV.

    Stage 1 — Basing:    Price near 30W MA, flat slope, after downtrend
    Stage 2 — Advancing: Price > 30W MA, rising slope  → LONG only
    Stage 3 — Topping:   Price near/below 30W MA after uptrend, flat slope
    Stage 4 — Declining: Price < 30W MA, falling slope → SHORT only

    Returns:
        {stage, direction, strength, ma_long, ma_short, slope_pct,
         above_ma, volume_expansion}
    """
    empty = {
        "stage": None, "direction": "NEUTRAL", "strength": "weak",
        "ma_long": None, "ma_short": None, "slope_pct": None,
        "above_ma": None, "volume_expansion": False,
    }

    if weekly_df.empty or "Close" not in weekly_df.columns:
        return empty
    if len(weekly_df) < config.WEINSTEIN_MA_LONG + 5:
        return empty

    close  = weekly_df["Close"]
    volume = weekly_df.get("Volume", pd.Series(dtype=float))

    ma_long  = close.rolling(config.WEINSTEIN_MA_LONG).mean()
    ma_short = close.rolling(config.WEINSTEIN_MA_SHORT).mean()

    current_close   = _safe_last(close)
    current_ma_long = _safe_last(ma_long)
    current_ma_short = _safe_last(ma_short)
    prev_ma_short    = _safe_last(ma_short, 2)

    if None in (current_close, current_ma_long, current_ma_short, prev_ma_short):
        return empty

    above_ma = current_close > current_ma_long

    # Slope: change in short MA vs previous period, normalised by MA value
    slope_pct = (current_ma_short - prev_ma_short) / prev_ma_short if prev_ma_short else 0.0
    is_flat    = abs(slope_pct) < config.WEINSTEIN_SLOPE_FLAT
    is_rising  = slope_pct > config.WEINSTEIN_SLOPE_FLAT
    is_falling = slope_pct < -config.WEINSTEIN_SLOPE_FLAT

    # Volume expansion vs 10-week average
    vol_expansion = False
    if not volume.empty and len(volume.dropna()) >= config.WEINSTEIN_MA_SHORT:
        current_vol = _safe_last(volume)
        avg_vol     = _safe_last(volume.rolling(config.WEINSTEIN_MA_SHORT).mean())
        if current_vol and avg_vol and avg_vol > 0:
            vol_expansion = current_vol > config.WEINSTEIN_VOL_MULT * avg_vol

    # Stage detection
    if above_ma and is_rising:
        stage     = 2
        direction = "LONG"
        strength  = "strong" if vol_expansion else "moderate"
    elif above_ma and is_flat:
        stage     = 3
        direction = "NEUTRAL"
        strength  = "weak"
    elif not above_ma and is_falling:
        stage     = 4
        direction = "SHORT"
        strength  = "strong" if vol_expansion else "moderate"
    else:
        # Stage 1: below or near MA, flat or curling up from downtrend
        stage     = 1
        direction = "NEUTRAL"
        strength  = "weak"

    return {
        "stage":            stage,
        "direction":        direction,
        "strength":         strength,
        "ma_long":          round(current_ma_long, 4),
        "ma_short":         round(current_ma_short, 4),
        "slope_pct":        round(slope_pct * 100, 4),
        "above_ma":         above_ma,
        "volume_expansion": vol_expansion,
    }


# ---------------------------------------------------------------------------
# 2. Larry Williams COT Commercial Index
# ---------------------------------------------------------------------------

def calc_commercial_index(cot_df: pd.DataFrame, window: int = config.COT_WINDOW) -> dict:
    """
    Williams Commercial Index = (current_net - 52W_min) / (52W_max - 52W_min) × 100

    > 75 → commercials net long → BULLISH (smart money loaded long)
    < 25 → commercials net short → BEARISH (smart money hedged short)

    Returns:
        {commercial_index, comm_net, signal, signal_strength, available}
    """
    empty = {
        "commercial_index": None,
        "comm_net":         None,
        "signal":           "NEUTRAL",
        "signal_strength":  "none",
        "available":        False,
    }

    if cot_df.empty or "comm_net" not in cot_df.columns:
        return empty

    comm_net = cot_df["comm_net"].dropna()
    if len(comm_net) < 4:
        return empty

    current = float(comm_net.iloc[-1])
    window_data = comm_net.tail(window)
    mn, mx = float(window_data.min()), float(window_data.max())

    if mx == mn:
        return {**empty, "comm_net": int(current), "available": True,
                "commercial_index": 50.0}

    ci = (current - mn) / (mx - mn) * 100.0

    if ci >= config.COT_COMMERCIAL_BULLISH:
        signal         = "BULLISH"
        signal_strength = "strong" if ci >= 85 else "moderate"
    elif ci <= config.COT_COMMERCIAL_BEARISH:
        signal         = "BEARISH"
        signal_strength = "strong" if ci <= 15 else "moderate"
    else:
        signal         = "NEUTRAL"
        signal_strength = "none"

    return {
        "commercial_index": round(ci, 1),
        "comm_net":         int(current),
        "signal":           signal,
        "signal_strength":  signal_strength,
        "available":        True,
        "history":          comm_net,   # keep for chart rendering
    }


# ---------------------------------------------------------------------------
# 3. Williams %R
# ---------------------------------------------------------------------------

def calc_williams_r(df: pd.DataFrame, period: int = config.WILLIAMS_R_PERIOD) -> dict:
    """
    Williams %R = (Highest High - Close) / (Highest High - Lowest Low) × -100

    Returns:
        {value, oversold, overbought}
    """
    empty = {"value": None, "oversold": False, "overbought": False}

    needed = {"High", "Low", "Close"}
    if df.empty or not needed.issubset(df.columns) or len(df) < period:
        return empty

    hh = df["High"].rolling(period).max()
    ll = df["Low"].rolling(period).min()

    denom = hh - ll
    denom = denom.replace(0, np.nan)

    wr = ((hh - df["Close"]) / denom) * -100
    val = _safe_last(wr)

    if val is None:
        return empty

    return {
        "value":      round(val, 2),
        "oversold":   val <= config.WILLIAMS_R_OVERSOLD,
        "overbought": val >= config.WILLIAMS_R_OVERBOUGHT,
    }


# ---------------------------------------------------------------------------
# 4. ATR (used by ICT engine and trade_generator for stop sizing)
# ---------------------------------------------------------------------------

def calc_atr(df: pd.DataFrame, period: int = config.ICT_ATR_PERIOD) -> float | None:
    """Wilder ATR. Returns most recent value or None."""
    needed = {"High", "Low", "Close"}
    if df.empty or not needed.issubset(df.columns) or len(df) < period + 1:
        return None

    high  = df["High"]
    low   = df["Low"]
    prev_close = df["Close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_series = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    result = _safe_last(atr_series)
    return round(result, 6) if result is not None else None


# ---------------------------------------------------------------------------
# Master indicator builder — one call per asset
# ---------------------------------------------------------------------------

def build_indicators(asset_key: str, data: dict) -> dict:
    """
    Build all indicators for a single asset from the master data dict.
    Returns:
    {
        "weinstein":  calc_weinstein_stage result,
        "cot":        calc_commercial_index result,
        "williams_r": calc_williams_r result (4H),
        "atr_4h":     ATR on 4H data,
        "price":      current close (4H last bar),
        "price_daily":current close (daily last bar),
    }
    """
    weekly_df = data["weekly"].get(asset_key, pd.DataFrame())
    daily_df  = data["daily"].get(asset_key, pd.DataFrame())
    df_4h     = data["4h"].get(asset_key, pd.DataFrame())
    cot_df    = data["cot"].get(asset_key, pd.DataFrame())

    def _last_close(df: pd.DataFrame) -> float | None:
        if df.empty or "Close" not in df.columns:
            return None
        v = df["Close"].dropna()
        return float(v.iloc[-1]) if not v.empty else None

    return {
        "weinstein":   calc_weinstein_stage(weekly_df),
        "cot":         calc_commercial_index(cot_df),
        "williams_r":  calc_williams_r(df_4h),
        "atr_4h":      calc_atr(df_4h),
        "price":       _last_close(df_4h) or _last_close(daily_df),
        "price_daily": _last_close(daily_df),
    }
