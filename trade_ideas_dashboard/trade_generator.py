# =============================================================================
# Trade Ideas Dashboard — Trade Generator
# =============================================================================
"""
Assembles a full trade idea per asset from scored confluence signals.

For each asset the generator:
  1. Evaluates LONG and SHORT independently
  2. Scores each with the confluence engine
  3. Filters out grade C ideas
  4. Selects the higher-scoring direction if both pass
  5. Computes entry, stop, and two targets from ICT structure + ATR sizing
  6. Returns a structured TradeIdea dict ready for the UI
"""
import math
from datetime import datetime

import config
import indicators as ind
import ict_engine  as ict
import scoring


# ---------------------------------------------------------------------------
# Entry / Stop / Target calculation helpers
# ---------------------------------------------------------------------------

def _calc_entry_long(ict_signals: dict, current_price: float) -> float:
    """
    Preferred entry for a long:
    1. Bottom of nearest bullish OB
    2. Bottom of nearest bullish FVG
    3. Current price (market entry)
    """
    ob = ict_signals.get("nearest_ob_long")
    if ob:
        return round(ob["ob_low"], 6)

    fvg = ict_signals.get("nearest_fvg_long")
    if fvg:
        return round(fvg["fvg_low"], 6)

    return round(current_price, 6)


def _calc_entry_short(ict_signals: dict, current_price: float) -> float:
    ob = ict_signals.get("nearest_ob_short")
    if ob:
        return round(ob["ob_high"], 6)

    fvg = ict_signals.get("nearest_fvg_short")
    if fvg:
        return round(fvg["fvg_high"], 6)

    return round(current_price, 6)


def _calc_stop_long(entry: float, ict_signals: dict, atr: float | None) -> float:
    """
    Stop for long: below nearest bullish OB low, or 1.5× ATR below entry.
    """
    ob = ict_signals.get("nearest_ob_long")
    if ob:
        ob_range = ob["ob_high"] - ob["ob_low"]
        buffer   = ob_range * 0.5 if ob_range > 0 else (entry * 0.003)
        return round(ob["ob_low"] - buffer, 6)

    if atr:
        return round(entry - 1.5 * atr, 6)

    return round(entry * 0.994, 6)


def _calc_stop_short(entry: float, ict_signals: dict, atr: float | None) -> float:
    ob = ict_signals.get("nearest_ob_short")
    if ob:
        ob_range = ob["ob_high"] - ob["ob_low"]
        buffer   = ob_range * 0.5 if ob_range > 0 else (entry * 0.003)
        return round(ob["ob_high"] + buffer, 6)

    if atr:
        return round(entry + 1.5 * atr, 6)

    return round(entry * 1.006, 6)


def _calc_targets(entry: float, stop: float, direction: str) -> tuple[float, float]:
    """
    Target1 = 2× RR from entry
    Target2 = 4× RR from entry
    """
    risk = abs(entry - stop)
    if risk == 0:
        risk = entry * 0.003

    if direction == "LONG":
        t1 = round(entry + config.DEFAULT_RR_TARGET1 * risk, 6)
        t2 = round(entry + config.DEFAULT_RR_TARGET2 * risk, 6)
    else:
        t1 = round(entry - config.DEFAULT_RR_TARGET1 * risk, 6)
        t2 = round(entry - config.DEFAULT_RR_TARGET2 * risk, 6)

    return t1, t2


def _calc_rr(entry: float, stop: float, target: float) -> float:
    risk   = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)


def _calc_position_size(
    account_size: float,
    risk_pct: float,
    entry: float,
    stop: float,
    pip_value: float = 1.0,
) -> float:
    """
    Units to risk at risk_pct of account.
    position_size = (account * risk_pct/100) / (entry - stop) / pip_value
    """
    risk_amount = account_size * risk_pct / 100.0
    risk_pips   = abs(entry - stop) / pip_value
    if risk_pips == 0:
        return 0.0
    return round(risk_amount / risk_pips, 2)


# ---------------------------------------------------------------------------
# Single-asset trade idea builder
# ---------------------------------------------------------------------------

def _build_idea(
    asset_key: str,
    direction: str,
    ind_result: dict,
    ict_signals: dict,
    score_result: dict,
) -> dict | None:
    """
    Build a full trade idea dict.  Returns None if not displayable.
    """
    if not score_result["displayable"]:
        return None

    current_price = ict_signals.get("current_price") or ind_result.get("price") or 0.0
    atr           = ind_result.get("atr_4h")
    asset_cfg     = config.ASSETS[asset_key]

    if direction == "LONG":
        entry = _calc_entry_long(ict_signals, current_price)
        stop  = _calc_stop_long(entry, ict_signals, atr)
    else:
        entry = _calc_entry_short(ict_signals, current_price)
        stop  = _calc_stop_short(entry, ict_signals, atr)

    target1, target2 = _calc_targets(entry, stop, direction)
    rr1 = _calc_rr(entry, stop, target1)
    rr2 = _calc_rr(entry, stop, target2)

    # Daily price change
    price_daily = ind_result.get("price_daily")
    daily_chg_pct = None
    if price_daily and current_price and price_daily != 0:
        daily_chg_pct = round((current_price / price_daily - 1) * 100, 2)

    return {
        "asset_key":    asset_key,
        "asset_name":   asset_cfg["name"],
        "direction":    direction,
        "grade":        score_result["grade"],
        "points":       score_result["points"],
        "entry":        entry,
        "stop":         stop,
        "target1":      target1,
        "target2":      target2,
        "rr1":          rr1,
        "rr2":          rr2,
        "current_price": current_price,
        "daily_chg_pct": daily_chg_pct,
        "atr_4h":       atr,
        "killzone":     ict_signals.get("killzone", {}),
        "factors":      score_result["factors"],
        "rationale":    score_result["rationale"],
        "weinstein":    ind_result["weinstein"],
        "cot":          ind_result["cot"],
        "williams_r":   ind_result["williams_r"],
        "ict":          ict_signals,
        "pip":          asset_cfg.get("pip", 0.0001),
        "generated_at": datetime.now().isoformat(timespec="minutes"),
    }


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_trade_ideas(data: dict) -> list[dict]:
    """
    Generate trade ideas for all assets.
    Returns list of trade idea dicts, sorted by grade (A+ > A > B) then points.
    """
    grade_order = {"A+": 0, "A": 1, "B": 2, "C": 3}
    ideas = []

    for asset_key in config.ASSETS:
        try:
            ind_result  = ind.build_indicators(asset_key, data)
            ict_signals = ict.build_ict_signals(asset_key, data)
            weinstein   = ind_result["weinstein"]
            cot         = ind_result["cot"]
            wr          = ind_result["williams_r"]

            for direction in ("LONG", "SHORT"):
                score_result = scoring.score_confluence(direction, weinstein, cot, wr, ict_signals)
                idea = _build_idea(asset_key, direction, ind_result, ict_signals, score_result)
                if idea is not None:
                    ideas.append(idea)

        except Exception:
            # Never crash the whole dashboard for one asset
            continue

    ideas.sort(key=lambda x: (grade_order.get(x["grade"], 9), -x["points"]))
    return ideas


def calc_position_size_for_idea(
    idea: dict,
    account_size: float = config.DEFAULT_ACCOUNT_SIZE,
    risk_pct: float = config.DEFAULT_RISK_PCT,
) -> dict:
    """
    Compute position sizing for a trade idea.
    Returns {units, risk_amount, risk_pct, account_size}.
    """
    units = _calc_position_size(
        account_size,
        risk_pct,
        idea["entry"],
        idea["stop"],
        idea["pip"],
    )
    risk_amount = round(account_size * risk_pct / 100, 2)

    return {
        "units":        units,
        "risk_amount":  risk_amount,
        "risk_pct":     risk_pct,
        "account_size": account_size,
    }
