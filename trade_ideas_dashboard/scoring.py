# =============================================================================
# Trade Ideas Dashboard — Confluence Scoring (Mark Douglas Grading)
# =============================================================================
"""
Scores each potential trade by counting how many independent confluence factors
align. Translates total points into an A+/A/B/C grade per Mark Douglas's
probability-based thinking: more confluences = higher probability setup.

Point system (see config.CONFLUENCE_POINTS):
  Weinstein stage aligned      +2
  COT commercial signal aligned +2
  Williams %R in entry zone    +1
  Price in ICT OTE zone        +1
  4H Order Block at entry      +1
  4H Fair Value Gap at entry   +1
  Active killzone session      +1
  Daily bias aligned           +1
  Max possible: 10
"""
import config


# ---------------------------------------------------------------------------
# Individual signal checks
# ---------------------------------------------------------------------------

def _weinstein_aligned(weinstein: dict, direction: str) -> bool:
    if direction == "LONG":
        return weinstein.get("stage") == 2 and weinstein.get("direction") == "LONG"
    elif direction == "SHORT":
        return weinstein.get("stage") == 4 and weinstein.get("direction") == "SHORT"
    return False


def _cot_aligned(cot: dict, direction: str) -> bool:
    if not cot.get("available", False):
        return False
    signal = cot.get("signal", "NEUTRAL")
    if direction == "LONG":
        return signal == "BULLISH"
    elif direction == "SHORT":
        return signal == "BEARISH"
    return False


def _williams_r_entry(wr: dict, direction: str) -> bool:
    if direction == "LONG":
        return wr.get("oversold", False)
    elif direction == "SHORT":
        return wr.get("overbought", False)
    return False


def _ote_aligned(ict: dict, direction: str) -> bool:
    """Price is currently in the OTE retracement zone."""
    return bool(ict.get("price_in_ote", False))


def _order_block_present(ict: dict, direction: str) -> bool:
    if direction == "LONG":
        return ict.get("nearest_ob_long") is not None
    elif direction == "SHORT":
        return ict.get("nearest_ob_short") is not None
    return False


def _fvg_present(ict: dict, direction: str) -> bool:
    if direction == "LONG":
        return ict.get("nearest_fvg_long") is not None
    elif direction == "SHORT":
        return ict.get("nearest_fvg_short") is not None
    return False


def _killzone_active(ict: dict) -> bool:
    return bool(ict.get("killzone", {}).get("active", False))


def _daily_bias_aligned(ict: dict, direction: str) -> bool:
    bias = ict.get("daily_bias", {}).get("bias", "NEUTRAL")
    if direction == "LONG":
        return bias == "BULLISH"
    elif direction == "SHORT":
        return bias == "BEARISH"
    return False


# ---------------------------------------------------------------------------
# Main confluence scorer
# ---------------------------------------------------------------------------

def score_confluence(
    direction: str,
    weinstein: dict,
    cot: dict,
    wr: dict,
    ict: dict,
) -> dict:
    """
    Accumulate confluence points and assign a grade.

    Parameters
    ----------
    direction : "LONG" or "SHORT"
    weinstein : result of indicators.calc_weinstein_stage()
    cot       : result of indicators.calc_commercial_index()
    wr        : result of indicators.calc_williams_r()
    ict       : result of ict_engine.build_ict_signals()

    Returns
    -------
    {
        "points":      int,
        "grade":       "A+" | "A" | "B" | "C",
        "displayable": bool  (False if grade C),
        "factors":     dict of {factor_name: (points_awarded, bool_signal)},
        "rationale":   str,
    }
    """
    pts = config.CONFLUENCE_POINTS

    factors: dict[str, tuple[int, bool]] = {
        "weinstein_stage": (pts["weinstein_stage"], _weinstein_aligned(weinstein, direction)),
        "cot_commercial":  (pts["cot_commercial"],  _cot_aligned(cot, direction)),
        "williams_r":      (pts["williams_r"],       _williams_r_entry(wr, direction)),
        "ict_ote":         (pts["ict_ote"],          _ote_aligned(ict, direction)),
        "order_block":     (pts["order_block"],      _order_block_present(ict, direction)),
        "fvg":             (pts["fvg"],              _fvg_present(ict, direction)),
        "killzone":        (pts["killzone"],         _killzone_active(ict)),
        "daily_bias":      (pts["daily_bias"],       _daily_bias_aligned(ict, direction)),
    }

    total = sum(p for (p, sig) in factors.values() if sig)

    # Grade
    thresholds = config.GRADE_THRESHOLDS
    if total >= thresholds["A+"]:
        grade = "A+"
    elif total >= thresholds["A"]:
        grade = "A"
    elif total >= thresholds["B"]:
        grade = "B"
    else:
        grade = "C"

    displayable = total >= config.GRADE_MIN_DISPLAY

    # Rationale string
    active_factors = [k for k, (p, sig) in factors.items() if sig]
    rationale = _build_rationale(direction, grade, total, active_factors, weinstein, cot, ict)

    return {
        "points":      total,
        "grade":       grade,
        "displayable": displayable,
        "factors":     factors,
        "rationale":   rationale,
    }


def _build_rationale(
    direction: str,
    grade: str,
    points: int,
    active_factors: list[str],
    weinstein: dict,
    cot: dict,
    ict: dict,
) -> str:
    """Generate a concise human-readable rationale string."""
    lines = []

    stage = weinstein.get("stage")
    stage_label = config.STAGE_LABELS.get(stage, f"Stage {stage}")
    if "weinstein_stage" in active_factors:
        lines.append(f"{stage_label} — institutional trend aligned {direction}")

    ci = cot.get("commercial_index")
    if ci is not None and "cot_commercial" in active_factors:
        side = "long" if direction == "LONG" else "short"
        lines.append(f"Commercial hedgers at {ci:.0f}% → smart money net {side}")

    if "williams_r" in active_factors:
        zone = "oversold" if direction == "LONG" else "overbought"
        lines.append(f"Williams %R in {zone} zone — entry timing favourable")

    if "ict_ote" in active_factors:
        lines.append("Price in OTE zone (0.618–0.705 Fibonacci retracement)")

    if "order_block" in active_factors:
        ob_type = "bullish" if direction == "LONG" else "bearish"
        lines.append(f"4H {ob_type} order block acting as institutional support")

    if "fvg" in active_factors:
        lines.append("Fair Value Gap present — imbalance to fill")

    kz = ict.get("killzone", {})
    if "killzone" in active_factors and kz.get("active"):
        lines.append(f"Active session: {kz.get('session_name')} — smart money participating")

    if "daily_bias" in active_factors:
        bias = ict.get("daily_bias", {}).get("bias", "")
        lines.append(f"Daily {bias.lower()} bias confirmed via PDH/PDL sweep")

    if not lines:
        lines.append(f"Grade {grade} setup with {points} confluence points — await additional confirmation")

    return ". ".join(lines) + "."
