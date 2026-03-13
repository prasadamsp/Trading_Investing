# =============================================================================
# Trade Ideas Dashboard — ICT Engine (4H + Daily)
# =============================================================================
"""
Applies Inner Circle Trader concepts on 4H and Daily timeframes:
  - Order Block detection (4H)
  - Fair Value Gap detection (4H)
  - OTE zone calculation (Fibonacci 0.618–0.705)
  - Swing point detection
  - Daily bias from PDH/PDL analysis
  - Killzone / session status
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config


# ---------------------------------------------------------------------------
# Swing Point Detection
# ---------------------------------------------------------------------------

def find_swing_points(df: pd.DataFrame, order: int = config.ICT_SWING_ORDER) -> dict:
    """
    Fractal swing high/low detection.
    A swing high at bar i: df['High'][i] is max among i-order..i+order bars.
    Returns {"highs": pd.Series, "lows": pd.Series} indexed by date.
    """
    empty = {"highs": pd.Series(dtype=float), "lows": pd.Series(dtype=float)}

    if df.empty or len(df) < 2 * order + 1:
        return empty

    highs: dict = {}
    lows:  dict = {}

    high_arr = df["High"].values
    low_arr  = df["Low"].values
    idx      = df.index

    for i in range(order, len(df) - order):
        window_h = high_arr[i - order : i + order + 1]
        window_l = low_arr[i  - order : i + order + 1]
        if high_arr[i] == window_h.max():
            highs[idx[i]] = float(high_arr[i])
        if low_arr[i] == window_l.min():
            lows[idx[i]] = float(low_arr[i])

    return {
        "highs": pd.Series(highs, dtype=float),
        "lows":  pd.Series(lows,  dtype=float),
    }


def _last_major_swing(df: pd.DataFrame, order: int = config.ICT_SWING_ORDER) -> dict:
    """Return the most recent confirmed swing high and swing low."""
    swings = find_swing_points(df, order)
    sh = float(swings["highs"].iloc[-1]) if not swings["highs"].empty else None
    sl = float(swings["lows"].iloc[-1])  if not swings["lows"].empty  else None
    return {"swing_high": sh, "swing_low": sl}


# ---------------------------------------------------------------------------
# Order Block Detection (4H)
# ---------------------------------------------------------------------------

def find_order_blocks_4h(df: pd.DataFrame, lookback: int = config.ICT_OB_LOOKBACK) -> list[dict]:
    """
    Find institutional order blocks on 4H data.

    Bullish OB: Last bearish candle before a strong bullish impulse.
    Bearish OB: Last bullish candle before a strong bearish impulse.

    Returns list of dicts:
        {type, ob_high, ob_low, ob_open, ob_close, bar_date,
         impulse_pct, mitigated}
    sorted newest-first.
    """
    if df.empty or len(df) < lookback + 3:
        return []

    recent = df.tail(lookback + 3).copy()
    opens  = recent["Open"].values
    highs  = recent["High"].values
    lows   = recent["Low"].values
    closes = recent["Close"].values
    idx    = recent.index

    obs = []
    n = len(recent)

    for i in range(1, n - 2):
        candle_range = highs[i] - lows[i]
        if candle_range == 0:
            continue

        # Next 2-bar impulse
        next_move = closes[i + 2] - closes[i]
        impulse_pct = abs(next_move) / closes[i]

        if impulse_pct < config.ICT_OB_MIN_IMPULSE_PCT:
            continue

        # Bullish OB: bearish candle → strong up impulse
        if closes[i] < opens[i] and next_move > 0:
            obs.append({
                "type":        "bullish",
                "ob_high":     float(highs[i]),
                "ob_low":      float(lows[i]),
                "ob_open":     float(opens[i]),
                "ob_close":    float(closes[i]),
                "bar_date":    idx[i],
                "impulse_pct": round(impulse_pct * 100, 2),
                "mitigated":   False,
            })

        # Bearish OB: bullish candle → strong down impulse
        elif closes[i] > opens[i] and next_move < 0:
            obs.append({
                "type":        "bearish",
                "ob_high":     float(highs[i]),
                "ob_low":      float(lows[i]),
                "ob_open":     float(opens[i]),
                "ob_close":    float(closes[i]),
                "bar_date":    idx[i],
                "impulse_pct": round(impulse_pct * 100, 2),
                "mitigated":   False,
            })

    # Mark mitigated OBs (price traded into the OB body afterwards)
    current_close = float(closes[-1])
    for ob in obs:
        if ob["type"] == "bullish" and current_close < ob["ob_low"]:
            ob["mitigated"] = True
        elif ob["type"] == "bearish" and current_close > ob["ob_high"]:
            ob["mitigated"] = True

    # Return only unmitigated, sorted newest first
    active = [o for o in obs if not o["mitigated"]]
    return sorted(active, key=lambda x: x["bar_date"], reverse=True)


# ---------------------------------------------------------------------------
# Fair Value Gap Detection (4H)
# ---------------------------------------------------------------------------

def find_fvgs_4h(df: pd.DataFrame, lookback: int = config.ICT_FVG_LOOKBACK) -> list[dict]:
    """
    Fair Value Gaps on 4H data.
    Bullish FVG: candle[i-1].High < candle[i+1].Low  (gap up)
    Bearish FVG: candle[i-1].Low  > candle[i+1].High (gap down)

    Returns list of dicts sorted newest-first:
        {type, fvg_high, fvg_low, bar_date, filled}
    """
    if df.empty or len(df) < lookback + 2:
        return []

    recent = df.tail(lookback + 2).copy()
    highs  = recent["High"].values
    lows   = recent["Low"].values
    closes = recent["Close"].values
    idx    = recent.index

    fvgs = []
    n = len(recent)

    for i in range(1, n - 1):
        # Bullish FVG
        if lows[i + 1] > highs[i - 1]:
            fvgs.append({
                "type":     "bullish",
                "fvg_high": float(lows[i + 1]),
                "fvg_low":  float(highs[i - 1]),
                "bar_date": idx[i],
                "filled":   False,
            })
        # Bearish FVG
        elif highs[i + 1] < lows[i - 1]:
            fvgs.append({
                "type":     "bearish",
                "fvg_high": float(lows[i - 1]),
                "fvg_low":  float(highs[i + 1]),
                "bar_date": idx[i],
                "filled":   False,
            })

    # Mark filled FVGs
    current_close = float(closes[-1])
    for fvg in fvgs:
        if fvg["type"] == "bullish" and current_close < fvg["fvg_low"]:
            fvg["filled"] = True
        elif fvg["type"] == "bearish" and current_close > fvg["fvg_high"]:
            fvg["filled"] = True

    active = [f for f in fvgs if not f["filled"]]
    return sorted(active, key=lambda x: x["bar_date"], reverse=True)


# ---------------------------------------------------------------------------
# OTE Zone (Fibonacci 0.618–0.705)
# ---------------------------------------------------------------------------

def calc_ote_zone(swing_high: float, swing_low: float) -> dict:
    """
    Optimal Trade Entry zone between 0.618 and 0.705 Fibonacci retracement.
    Returns {ote_high, ote_low, fib_levels} for both long and short setups.
    """
    rng = swing_high - swing_low

    if rng <= 0:
        return {"ote_high": None, "ote_low": None, "fib_levels": {}}

    fib_levels = {
        level: round(swing_high - level * rng, 6)
        for level in config.ICT_FIB_LEVELS
    }

    # OTE retracement for a long: price retraces down into 0.618–0.705 zone
    ote_high = round(swing_high - config.ICT_OTE_LOW  * rng, 6)
    ote_low  = round(swing_high - config.ICT_OTE_HIGH * rng, 6)

    return {
        "ote_high":   ote_high,
        "ote_low":    ote_low,
        "fib_levels": fib_levels,
        "swing_high": swing_high,
        "swing_low":  swing_low,
    }



# ---------------------------------------------------------------------------
# Daily Bias (PDH/PDL sweep analysis)
# ---------------------------------------------------------------------------

def get_daily_bias(daily_df: pd.DataFrame) -> dict:
    """
    Determine directional daily bias from previous day's High/Low (PDH/PDL).

    Logic:
    - If today's price has already swept PDH (traded above it) → short-term bearish reaction likely
    - If today's price has already swept PDL (traded below it) → short-term bullish reaction likely
    - PDH/PDL intact: neutral, look for which one will be swept

    Returns:
        {bias, pdh, pdl, swept_pdh, swept_pdl, current_price}
    """
    empty = {
        "bias": "NEUTRAL", "pdh": None, "pdl": None,
        "swept_pdh": False, "swept_pdl": False, "current_price": None,
    }

    if daily_df.empty or len(daily_df) < 2:
        return empty

    needed = {"High", "Low", "Close"}
    if not needed.issubset(daily_df.columns):
        return empty

    prev       = daily_df.iloc[-2]
    current    = daily_df.iloc[-1]
    pdh        = float(prev["High"])
    pdl        = float(prev["Low"])
    curr_high  = float(current["High"])
    curr_low   = float(current["Low"])
    curr_close = float(current["Close"])

    swept_pdh = curr_high > pdh
    swept_pdl = curr_low  < pdl

    # Determine bias
    if swept_pdl and not swept_pdh:
        bias = "BULLISH"    # liquidity below swept, likely continuing up
    elif swept_pdh and not swept_pdl:
        bias = "BEARISH"    # liquidity above swept, likely continuing down
    elif swept_pdh and swept_pdl:
        bias = "NEUTRAL"    # both swept — indecision / re-accumulation
    else:
        # Neither swept yet: bias is toward where liquidity hasn't been taken
        bias = "NEUTRAL"

    return {
        "bias":          bias,
        "pdh":           round(pdh, 6),
        "pdl":           round(pdl, 6),
        "swept_pdh":     swept_pdh,
        "swept_pdl":     swept_pdl,
        "current_price": round(curr_close, 6),
    }


# ---------------------------------------------------------------------------
# Killzone / Session Status
# ---------------------------------------------------------------------------

def get_killzone_status(now_utc: datetime | None = None) -> dict:
    """
    Returns the currently active killzone session (if any).

    Returns:
        {active: bool, session_name: str | None, minutes_to_next: int,
         next_session: str, sessions: list}
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Strip timezone for comparison
    h = now_utc.hour
    m = now_utc.minute
    now_minutes = h * 60 + m

    active_session = None
    for (sh, sm, eh, em, name) in config.KILLZONES:
        start_min = sh * 60 + sm
        end_min   = eh * 60 + em
        if start_min <= now_minutes < end_min:
            active_session = name
            break

    # Find next session
    sessions_ordered = config.KILLZONES
    next_session = None
    minutes_to_next = None

    for (sh, sm, eh, em, name) in sessions_ordered:
        start_min = sh * 60 + sm
        if start_min > now_minutes:
            next_session    = name
            minutes_to_next = start_min - now_minutes
            break

    # Wrap to next day's first session
    if next_session is None and sessions_ordered:
        sh, sm, _, _, name = sessions_ordered[0]
        start_min       = sh * 60 + sm
        next_session    = name
        minutes_to_next = (24 * 60 - now_minutes) + start_min

    return {
        "active":          active_session is not None,
        "session_name":    active_session,
        "next_session":    next_session,
        "minutes_to_next": minutes_to_next,
        "current_utc":     now_utc.strftime("%H:%M UTC"),
        "sessions":        [s[4] for s in sessions_ordered],
    }


# ---------------------------------------------------------------------------
# Price-in-OTE check
# ---------------------------------------------------------------------------

def price_in_ote(current_price: float, ote_zone: dict, direction: str) -> bool:
    """
    Check whether current price is inside the OTE zone for a given direction.
    Long: price within [ote_low, ote_high] (retracement from swing high)
    """
    ote_high = ote_zone.get("ote_high")
    ote_low  = ote_zone.get("ote_low")

    if ote_high is None or ote_low is None:
        return False

    if direction == "LONG":
        return ote_low <= current_price <= ote_high
    elif direction == "SHORT":
        # For shorts, OTE from swing low to swing high → price retraces UP
        sh = ote_zone.get("swing_high")
        sl = ote_zone.get("swing_low")
        if sh is None or sl is None:
            return False
        rng = sh - sl
        ote_short_low  = sl + config.ICT_OTE_LOW  * rng
        ote_short_high = sl + config.ICT_OTE_HIGH * rng
        return ote_short_low <= current_price <= ote_short_high

    return False


# ---------------------------------------------------------------------------
# Master ICT signal builder — one call per asset
# ---------------------------------------------------------------------------

def build_ict_signals(asset_key: str, data: dict) -> dict:
    """
    Compute all ICT signals for a single asset.
    Returns:
    {
        "order_blocks":    list of active OBs (4H),
        "fvgs":            list of active FVGs (4H),
        "swing_points":    {highs, lows} (4H),
        "ote_zone":        dict (4H major swing),
        "daily_bias":      dict,
        "killzone":        dict,
        "price_in_ote":    bool (for current direction),
        "nearest_ob_long": first bullish OB (or None),
        "nearest_ob_short":first bearish OB (or None),
        "nearest_fvg_long": first bullish FVG (or None),
        "nearest_fvg_short":first bearish FVG (or None),
    }
    """
    df_4h     = data["4h"].get(asset_key, pd.DataFrame())
    daily_df  = data["daily"].get(asset_key, pd.DataFrame())

    obs       = find_order_blocks_4h(df_4h)
    fvgs      = find_fvgs_4h(df_4h)
    swings    = find_swing_points(df_4h)
    daily_bias = get_daily_bias(daily_df)
    killzone  = get_killzone_status()

    # OTE from last major swing
    sh = float(swings["highs"].iloc[-1]) if not swings["highs"].empty else None
    sl = float(swings["lows"].iloc[-1])  if not swings["lows"].empty  else None
    ote_zone = calc_ote_zone(sh, sl) if (sh and sl) else {}

    # Current price
    current_price = None
    if not df_4h.empty and "Close" in df_4h.columns:
        cp = df_4h["Close"].dropna()
        if not cp.empty:
            current_price = float(cp.iloc[-1])

    return {
        "order_blocks":    obs,
        "fvgs":            fvgs,
        "swing_points":    swings,
        "ote_zone":        ote_zone,
        "daily_bias":      daily_bias,
        "killzone":        killzone,
        "price_in_ote":    price_in_ote(current_price, ote_zone, daily_bias["bias"]) if current_price else False,
        "nearest_ob_long":  next((o for o in obs if o["type"] == "bullish"), None),
        "nearest_ob_short": next((o for o in obs if o["type"] == "bearish"), None),
        "nearest_fvg_long":  next((f for f in fvgs if f["type"] == "bullish"), None),
        "nearest_fvg_short": next((f for f in fvgs if f["type"] == "bearish"), None),
        "current_price":   current_price,
    }
