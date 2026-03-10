# =============================================================================
# Oil Weekly Bias Dashboard — Indicator Calculations
# =============================================================================
from datetime import datetime

import numpy as np
import pandas as pd

import config


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _safe_last(series: pd.Series, n: int = 1) -> float | None:
    """Return the last n-th value of a series, or None if too short."""
    s = series.dropna()
    if len(s) < n:
        return None
    return float(s.iloc[-n])


def pct_change_weekly(series: pd.Series) -> float | None:
    """Percent change last close vs previous close."""
    s = series.dropna()
    if len(s) < 2:
        return None
    return float((s.iloc[-1] / s.iloc[-2] - 1) * 100)


def yoy_change(series: pd.Series) -> float | None:
    """Year-over-year percent change using monthly FRED series."""
    s = series.dropna()
    if len(s) < 13:
        return None
    return float((s.iloc[-1] / s.iloc[-13] - 1) * 100)


# ---------------------------------------------------------------------------
# Moving Averages
# ---------------------------------------------------------------------------

def calc_moving_averages(close: pd.Series, periods: list[int] = config.WEEKLY_MA_PERIODS) -> dict:
    """Returns dict with MA values and price-vs-MA status per period."""
    result = {}
    price = _safe_last(close)
    if price is None:
        return result
    for p in periods:
        ma = close.rolling(p).mean()
        ma_val = _safe_last(ma)
        if ma_val is None:
            continue
        result[p] = {
            "ma":       round(ma_val, 2),
            "above":    price > ma_val,
            "pct_diff": round((price / ma_val - 1) * 100, 2),
        }
    return result


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def calc_rsi(close: pd.Series, period: int = config.RSI_PERIOD) -> float | None:
    """Wilder's RSI."""
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    return _safe_last(rsi)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def calc_macd(
    close: pd.Series,
    fast: int = config.MACD_FAST,
    slow: int = config.MACD_SLOW,
    signal: int = config.MACD_SIGNAL,
) -> dict:
    """Returns {macd_line, signal_line, histogram, bullish (bool), crossing_up (bool)}."""
    ema_fast    = close.ewm(span=fast,   adjust=False).mean()
    ema_slow    = close.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line

    m      = _safe_last(macd_line)
    s      = _safe_last(signal_line)
    h      = _safe_last(histogram)
    h_prev = _safe_last(histogram, 2)

    if None in (m, s, h):
        return {"macd_line": None, "signal_line": None, "histogram": None, "bullish": None}

    return {
        "macd_line":   round(m, 4),
        "signal_line": round(s, 4),
        "histogram":   round(h, 4),
        "bullish":     bool(h > 0),
        "crossing_up": bool(h > 0 and h_prev is not None and h_prev < 0),
    }


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

def calc_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    """Wilder ATR(period) from OHLCV DataFrame; returns most recent value or None."""
    needed = {"High", "Low", "Close"}
    if df.empty or not needed.issubset(df.columns) or len(df) < period + 1:
        return None
    high       = df["High"]
    low        = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    result = _safe_last(atr_series)
    return round(result, 4) if result is not None else None


# ---------------------------------------------------------------------------
# COT Index (percentile)
# ---------------------------------------------------------------------------

def calc_cot_index(cot_df: pd.DataFrame, window: int = config.COT_PERCENTILE_WINDOW) -> dict:
    """
    COT Index = percentile rank of current net speculator position over trailing `window` weeks.
    Returns {net_pos, cot_index (0-100), extreme_long (bool), extreme_short (bool)}
    """
    if cot_df.empty or "noncomm_net" not in cot_df.columns:
        return {"net_pos": None, "cot_index": None, "extreme_long": None, "extreme_short": None}

    net = cot_df["noncomm_net"].dropna()
    if len(net) < 2:
        return {"net_pos": None, "cot_index": None, "extreme_long": None, "extreme_short": None}

    current = float(net.iloc[-1])
    window_data = net.tail(window)
    mn, mx = window_data.min(), window_data.max()
    cot_index = float((current - mn) / (mx - mn) * 100) if mx != mn else 50.0

    return {
        "net_pos":       int(current),
        "cot_index":     round(cot_index, 1),
        "extreme_long":  cot_index > 80,
        "extreme_short": cot_index < 20,
    }


# ---------------------------------------------------------------------------
# ETF Flow (shares outstanding delta proxy)
# ---------------------------------------------------------------------------

def calc_etf_flow(prices: dict, etf_shares: dict) -> dict:
    """
    Approximate weekly energy ETF flow using weekly price change × AUM as directional proxy.
    Returns per-ETF and combined metrics for XLE, XOP, USO.
    """
    etf_keys = ["xle", "xop", "uso"]
    result   = {}
    total_flow_proxy = 0.0
    n_valid  = 0

    for key in etf_keys:
        close  = prices.get(key, pd.DataFrame()).get("Close", pd.Series())
        shares = etf_shares.get(key)
        price  = _safe_last(close)
        price_prev = _safe_last(close, 2)

        if price is None or price_prev is None:
            result[key] = {"price": None, "weekly_chg_pct": None,
                           "aum_m": None, "flow_direction": "unknown"}
            continue

        weekly_chg_pct = round((price / price_prev - 1) * 100, 2)
        aum_m = round(shares * price / 1e6, 1) if shares else None

        flow_direction = "inflow" if weekly_chg_pct > 0 else "outflow"
        total_flow_proxy += weekly_chg_pct
        n_valid += 1

        result[key] = {
            "price":           round(price, 2),
            "weekly_chg_pct":  weekly_chg_pct,
            "aum_m":           aum_m,
            "flow_direction":  flow_direction,
            "shares":          shares,
        }

    result["combined_flow_avg_pct"] = round(total_flow_proxy / n_valid, 2) if n_valid else None
    return result


# ---------------------------------------------------------------------------
# EIA Inventory Signal
# ---------------------------------------------------------------------------

def calc_eia_signals(eia: dict) -> dict:
    """
    Calculate weekly inventory draw/build for crude, gasoline, distillates.
    A draw (negative change) is bullish for oil; a build (positive) is bearish.
    Returns {crude_draw_mbbl, gasoline_draw_mbbl, distillate_draw_mbbl, crude_5yr_avg}
    """
    result = {}

    for key in ["crude", "gasoline", "distillate"]:
        s = eia.get(key, pd.Series())
        if s.empty or len(s) < 2:
            result[f"{key}_draw_mbbl"] = None
            result[f"{key}_level"] = None
        else:
            draw = float(s.iloc[-1] - s.iloc[-2])   # negative = draw (bullish)
            result[f"{key}_draw_mbbl"] = round(draw, 1)
            result[f"{key}_level"] = round(float(s.iloc[-1]), 1)

        # 5yr average level (52w × 5 periods back)
        if not s.empty and len(s) >= 5:
            result[f"{key}_5yr_avg"] = round(float(s.tail(260).mean()), 1)
        else:
            result[f"{key}_5yr_avg"] = None

    return result


# ---------------------------------------------------------------------------
# Crude Oil Imports Signal (monthly — YoY trend)
# ---------------------------------------------------------------------------

def calc_imports_signal(imports: pd.Series) -> dict:
    """
    Compute YoY direction of US crude oil imports (monthly EIA data).
    Rising imports = more supply arriving → mildly bearish for domestic crude prices.
    Falling imports = tighter supply → mildly bullish.
    Returns {latest_mbpd, yoy_pct, rising (bool), series}
    """
    s = imports.dropna()
    if s.empty:
        return {"latest_mbpd": None, "yoy_pct": None, "rising": None, "series": s}

    latest = float(s.iloc[-1])
    yoy = None
    rising = None
    if len(s) >= 13:
        prev_year = float(s.iloc[-13])
        if prev_year != 0:
            yoy = round((latest / prev_year - 1) * 100, 2)
            rising = yoy > 0

    return {
        "latest_mbpd": round(latest, 1),
        "yoy_pct":     yoy,
        "rising":      rising,
        "series":      s,
    }


# ---------------------------------------------------------------------------
# Brent-WTI Spread
# ---------------------------------------------------------------------------

def calc_brent_wti_spread(prices: dict) -> dict:
    """
    Brent minus WTI spread. Positive = Brent premium (geopolitical risk or export bottleneck).
    Negative = WTI premium (rare; excess Brent supply).
    """
    brent_close = prices.get("brent", pd.DataFrame()).get("Close", pd.Series())
    wti_close   = prices.get("wti",   pd.DataFrame()).get("Close", pd.Series())

    spread_series = (brent_close - wti_close).dropna()

    return {
        "spread":      round(float(spread_series.iloc[-1]), 2) if not spread_series.empty else None,
        "spread_prev": round(float(spread_series.iloc[-2]), 2) if len(spread_series) >= 2 else None,
        "widening":    bool(spread_series.iloc[-1] > spread_series.iloc[-2])
                       if len(spread_series) >= 2 else None,
        "series":      spread_series,
    }


# ---------------------------------------------------------------------------
# Seasonal Demand Model
# ---------------------------------------------------------------------------

def calc_seasonal_score() -> dict:
    """Return seasonal demand score based on current calendar month."""
    month = datetime.today().month
    score = config.SEASONAL_SCORES.get(month, 0.0)
    season_name = {
        1: "Heating Season", 2: "Heating Season", 3: "Maintenance Start",
        4: "Spring Maintenance", 5: "Driving Season", 6: "Peak Driving",
        7: "Peak Driving", 8: "Late Driving", 9: "Season Transition",
        10: "Fall Maintenance", 11: "Heating Resumes", 12: "Winter Demand",
    }.get(month, "")
    return {"score": score, "month": month, "season_name": season_name}


# ---------------------------------------------------------------------------
# OVX Signal (Oil Volatility Index)
# ---------------------------------------------------------------------------

def calc_ovx_signal(prices: dict) -> dict:
    """
    OVX (CBOE Crude Oil Volatility Index). High OVX = elevated uncertainty.
    Very high OVX spikes can precede reversals (mean-reversion signal).
    """
    ovx = prices.get("ovx", pd.DataFrame()).get("Close", pd.Series())
    val = _safe_last(ovx)
    chg = pct_change_weekly(ovx)

    return {
        "value":          val,
        "weekly_chg":     chg,
        "high_vol":       bool(val > config.OVX_HIGH_VOLATILITY)   if val else False,
        "very_high_vol":  bool(val > config.OVX_VERY_HIGH)         if val else False,
    }


# ---------------------------------------------------------------------------
# Macro snapshot
# ---------------------------------------------------------------------------

def calc_macro_snapshot(prices: dict, fred: dict) -> dict:
    """Build a single dict of current macro readings."""
    def last(s: pd.Series) -> float | None:
        return _safe_last(s) if not s.empty else None

    def delta(s: pd.Series) -> float | None:
        arr = s.dropna()
        if len(arr) < 2:
            return None
        return float(arr.iloc[-1] - arr.iloc[-2])

    dxy_close = prices.get("dxy", pd.DataFrame()).get("Close", pd.Series())

    def _resample_weekly(s: pd.Series) -> pd.Series:
        if s.empty or not isinstance(s.index, pd.DatetimeIndex):
            return pd.Series(dtype=float)
        return s.resample("W").last()

    t2y  = _resample_weekly(fred.get("treasury_2y",  pd.Series()))
    t10y = _resample_weekly(fred.get("treasury_10y", pd.Series()))

    t2y_val  = last(t2y)
    t10y_val = last(t10y)
    yield_curve = round(t10y_val - t2y_val, 3) if (t2y_val and t10y_val) else None
    yield_curve_prev = None
    if not t2y.empty and not t10y.empty:
        p2, p10 = _safe_last(t2y, 2), _safe_last(t10y, 2)
        yield_curve_prev = round(p10 - p2, 3) if (p2 and p10) else None

    return {
        "dxy": {
            "value":      last(dxy_close),
            "weekly_chg": pct_change_weekly(dxy_close),
        },
        "real_yield_10y": {
            "value": last(fred.get("real_yield_10y", pd.Series())),
            "delta": delta(fred.get("real_yield_10y", pd.Series())),
        },
        "breakeven_10y": {
            "value": last(fred.get("breakeven_10y", pd.Series())),
            "delta": delta(fred.get("breakeven_10y", pd.Series())),
        },
        "fed_funds": {
            "value": last(fred.get("fed_funds", pd.Series())),
            "delta": delta(fred.get("fed_funds", pd.Series())),
        },
        "cpi_yoy": {"value": yoy_change(fred.get("cpi_yoy", pd.Series()))},
        "pce_yoy": {"value": yoy_change(fred.get("pce_yoy", pd.Series()))},
        "treasury_2y":  {"value": t2y_val,  "delta": delta(t2y)},
        "treasury_10y": {"value": t10y_val, "delta": delta(t10y)},
        "yield_curve": {
            "value":      yield_curve,
            "prev":       yield_curve_prev,
            "steepening": (yield_curve > yield_curve_prev)
                          if (yield_curve and yield_curve_prev) else None,
        },
    }


# ---------------------------------------------------------------------------
# Supply snapshot
# ---------------------------------------------------------------------------

def calc_supply_snapshot(prices: dict, fred: dict, eia: dict, imports: pd.Series | None = None) -> dict:
    """Build supply/demand indicator snapshot: EIA inventories, rig count, seasonal, spread, imports."""
    rig_count_series = fred.get("rig_count", pd.Series())

    def last(s: pd.Series) -> float | None:
        return _safe_last(s) if not s.empty else None

    def delta(s: pd.Series) -> float | None:
        arr = s.dropna()
        if len(arr) < 2:
            return None
        return float(arr.iloc[-1] - arr.iloc[-2])

    if imports is None:
        imports = pd.Series(dtype=float)

    return {
        "eia":         calc_eia_signals(eia),
        "rig_count": {
            "value":       last(rig_count_series),
            "weekly_chg":  delta(rig_count_series),
            "series":      rig_count_series,
        },
        "seasonal":    calc_seasonal_score(),
        "brent_wti":   calc_brent_wti_spread(prices),
        "imports":     calc_imports_signal(imports),
    }


# ---------------------------------------------------------------------------
# Cross-asset snapshot
# ---------------------------------------------------------------------------

def calc_cross_asset_snapshot(prices: dict) -> dict:
    """Cross-asset indicators for oil: SPX, VIX, natural gas, heating oil, gold."""
    def _last(key: str) -> float | None:
        s = prices.get(key, pd.DataFrame()).get("Close", pd.Series())
        return _safe_last(s)

    def _chg(key: str) -> float | None:
        s = prices.get(key, pd.DataFrame()).get("Close", pd.Series())
        return pct_change_weekly(s)

    return {
        "vix":     {"value": _last("vix"),      "weekly_chg": _chg("vix")},
        "spx":     {"value": _last("spx"),      "weekly_chg": _chg("spx")},
        "natgas":  {"value": _last("natgas"),   "weekly_chg": _chg("natgas")},
        "heating": {"value": _last("heating"),  "weekly_chg": _chg("heating")},
        "eurusd":  {"value": _last("eurusd"),   "weekly_chg": _chg("eurusd")},
        "gold":    {"value": _last("gold"),     "weekly_chg": _chg("gold")},
    }


# ---------------------------------------------------------------------------
# Master indicator builder
# ---------------------------------------------------------------------------

def build_all_indicators(data: dict) -> dict:
    """Takes raw data dict from fetch_all_data() and returns fully computed indicator snapshot."""
    prices     = data["prices"]
    etf_shares = data["etf_shares"]
    fred       = data["fred"]
    eia        = data["eia"]
    imports    = data.get("imports", pd.Series(dtype=float))
    cot        = data["cot"]

    wti_close = prices.get("wti", pd.DataFrame()).get("Close", pd.Series())

    return {
        "wti_price":      _safe_last(wti_close),
        "wti_weekly_chg": pct_change_weekly(wti_close),
        "macro":          calc_macro_snapshot(prices, fred),
        "supply":         calc_supply_snapshot(prices, fred, eia, imports),
        "technical": {
            "moving_averages": calc_moving_averages(wti_close),
            "rsi":             calc_rsi(wti_close),
            "macd":            calc_macd(wti_close),
            "ovx":             calc_ovx_signal(prices),
        },
        "sentiment": {
            "cot":      calc_cot_index(cot),
            "cot_df":   cot,
            "etf":      calc_etf_flow(prices, etf_shares),
        },
        "cross_asset": calc_cross_asset_snapshot(prices),
        "prices":      prices,
    }
