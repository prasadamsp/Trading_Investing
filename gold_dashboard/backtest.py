# =============================================================================
# Gold ICT Trade Ideas — Walk-Forward Backtest & Parameter Optimizer
# =============================================================================
"""
Standalone script. Run from the gold_dashboard/ directory:
    python backtest.py            # full backtest + grid search
    python backtest.py --baseline # baseline only (no grid search)

Methodology
-----------
Walk-forward simulation: for each evaluation date t (every 5 bars), slice all
data strictly up to t (no look-ahead), call generate_ict_trades(), then check
the next 30 daily bars for trade outcome.

Bias score is approximated from weekly MA positions (price vs MA_20/50/200)
since the full scoring.py model requires FRED/COT APIs for every past date.

Outcome classification (conservative — SL takes priority over TP within a bar):
  NO_ENTRY : price never reached entry within max_bars
  EXPIRED  : entry triggered but neither SL nor TP hit within remaining bars
  SL       : stop triggered (loss = 1R)
  TP1      : first target hit (partial win)
  TP2      : second target hit (full win, implies TP1 was also hit)
  WAIT     : direction was WAIT — excluded from win-rate calculations
"""

import itertools
import sys
import os

# ── Make gold_dashboard importable when run directly ────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pandas as pd
import numpy as np
import data_fetcher
import ict_analysis
import config


# =============================================================================
# Section 1 — Data Acquisition
# =============================================================================

def fetch_backtest_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fetch extended data for backtesting (no Streamlit caching).

    Returns:
        (daily_df, weekly_df, monthly_df)
        daily_df  : ~500 bars of daily GC=F OHLCV (2 years)
        weekly_df : ~260 bars of weekly GC=F OHLCV (5 years)
        monthly_df: ~120 bars of monthly GC=F OHLCV (10 years)
    """
    print("Fetching market data …", flush=True)
    daily_df   = data_fetcher.fetch_daily_prices(days=730)
    weekly_df  = data_fetcher.fetch_weekly_gold_ohlcv()
    monthly_df = data_fetcher.fetch_monthly_prices()
    print(f"  daily  : {len(daily_df):>4} bars  "
          f"({daily_df.index[0].date()} to {daily_df.index[-1].date()})")
    print(f"  weekly : {len(weekly_df):>4} bars  "
          f"({weekly_df.index[0].date()} to {weekly_df.index[-1].date()})")
    print(f"  monthly: {len(monthly_df):>4} bars  "
          f"({monthly_df.index[0].date()} to {monthly_df.index[-1].date()})")
    return daily_df, weekly_df, monthly_df


# =============================================================================
# Section 2 — Rolling Technical Bias (price-only, no FRED/COT)
# =============================================================================

def calc_rolling_bias(
    weekly_df: pd.DataFrame,
    as_of_date: pd.Timestamp,
    ma_periods: tuple[int, int, int] = (20, 50, 200),
) -> float:
    """
    Compute a price-only bias score in [-1.0, +1.0] from weekly MA positions.

    Mirrors the TECHNICAL_SUB_WEIGHTS rationale in scoring.py:
        MA_20w  weight 0.25  (reactive short-term signal)
        MA_50w  weight 0.35  (intermediate trend)
        MA_200w weight 0.40  (long-term structural trend)

    Each MA contributes a soft component: pct_deviation / 5% clipped to ±1.
    This produces a continuous score rather than hard ±1 steps.
    """
    w = weekly_df[weekly_df.index <= as_of_date]["Close"].dropna()
    if len(w) < max(ma_periods):
        return 0.0

    price   = float(w.iloc[-1])
    weights = {ma_periods[0]: 0.25, ma_periods[1]: 0.35, ma_periods[2]: 0.40}
    score   = 0.0

    for period in ma_periods:
        ma_val = float(w.rolling(period).mean().iloc[-1])
        if ma_val == 0 or np.isnan(ma_val):
            continue
        pct_diff  = (price - ma_val) / ma_val
        component = max(-1.0, min(1.0, pct_diff / 0.05))
        score    += component * weights[period]

    return round(max(-1.0, min(1.0, score)), 4)


# =============================================================================
# Section 3 — Walk-Forward Simulation
# =============================================================================

def slice_data_as_of(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    as_of_date: pd.Timestamp,
    daily_lookback: int = 120,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Slice all three DataFrames to rows with index <= as_of_date (no look-ahead).
    daily_df is further trimmed to the last `daily_lookback` rows to match the
    local-window expectation of the ICT engine.
    """
    d = daily_df[daily_df.index <= as_of_date].tail(daily_lookback)
    w = weekly_df[weekly_df.index <= as_of_date]
    m = monthly_df[monthly_df.index <= as_of_date]
    return d, w, m


def classify_outcome(
    trade: dict,
    forward_bars: pd.DataFrame,
    max_bars: int = 30,
) -> dict:
    """
    Simulate a single trade against subsequent OHLCV bars.

    Returns a result dict with keys:
        outcome      : "TP1"|"TP2"|"SL"|"EXPIRED"|"WAIT"|"NO_ENTRY"
        rr_achieved  : float|None  (positive for wins, -1.0 for SL)
        bars_to_entry: int|None
        bars_held    : int|None
    """
    null = {"outcome": None, "rr_achieved": None,
            "bars_to_entry": None, "bars_held": None}

    direction = trade.get("direction", "WAIT")
    if direction == "WAIT":
        return {**null, "outcome": "WAIT"}

    entry   = trade.get("entry")
    stop    = trade.get("stop")
    target1 = trade.get("target1")
    target2 = trade.get("target2")

    if entry is None or stop is None or target1 is None:
        return {**null, "outcome": "NO_ENTRY"}

    fwd = forward_bars.head(max_bars)
    if fwd.empty:
        return {**null, "outcome": "NO_ENTRY"}

    is_long = (direction == "LONG")

    # ── Step 1: find entry bar ──────────────────────────────────────────
    entry_bar_idx = None
    for i, (_, bar) in enumerate(fwd.iterrows()):
        lo, hi = float(bar["Low"]), float(bar["High"])
        triggered = (lo <= entry <= hi) if is_long else (lo <= entry <= hi)
        if triggered:
            entry_bar_idx = i
            break

    if entry_bar_idx is None:
        return {**null, "outcome": "NO_ENTRY"}

    # ── Step 2: walk bars after entry for outcome ───────────────────────
    post_entry = fwd.iloc[entry_bar_idx:]
    tp1_hit = tp2_hit = sl_hit = False

    for bars_held, (_, bar) in enumerate(post_entry.iterrows()):
        lo, hi = float(bar["Low"]), float(bar["High"])

        if is_long:
            sl_triggered  = lo <= stop
            tp1_triggered = hi >= target1
            tp2_triggered = (target2 is not None) and (hi >= target2)
        else:
            sl_triggered  = hi >= stop
            tp1_triggered = lo <= target1
            tp2_triggered = (target2 is not None) and (lo <= target2)

        # SL priority within same bar (conservative assumption)
        if sl_triggered:
            sl_hit = True
            break
        if tp2_triggered and tp1_hit:
            tp2_hit = True
            break
        if tp1_triggered:
            tp1_hit = True
            # Don't break — keep checking for TP2 in subsequent bars

    # ── Determine outcome ────────────────────────────────────────────────
    risk = abs(entry - stop)
    if risk == 0:
        return {**null, "outcome": "NO_ENTRY"}

    if sl_hit:
        return {
            "outcome":       "SL",
            "rr_achieved":   -1.0,
            "bars_to_entry": entry_bar_idx,
            "bars_held":     bars_held,
        }
    if tp2_hit:
        rr = abs(target2 - entry) / risk if target2 else None
        return {
            "outcome":       "TP2",
            "rr_achieved":   round(rr, 2) if rr else None,
            "bars_to_entry": entry_bar_idx,
            "bars_held":     bars_held,
        }
    if tp1_hit:
        rr = abs(target1 - entry) / risk
        return {
            "outcome":       "TP1",
            "rr_achieved":   round(rr, 2),
            "bars_to_entry": entry_bar_idx,
            "bars_held":     bars_held,
        }

    return {
        "outcome":       "EXPIRED",
        "rr_achieved":   None,
        "bars_to_entry": entry_bar_idx,
        "bars_held":     max_bars - entry_bar_idx,
    }


def run_single_backtest(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    params: dict | None = None,
    step_bars: int = 5,
    forward_bars: int = 30,
    daily_lookback: int = 120,
) -> list[dict]:
    """
    Walk-forward loop over daily_df.

    For each evaluation index t (from 60 to end-forward_bars, step=step_bars):
      1. Slice data up to daily_df.index[t]
      2. Compute rolling bias from weekly data
      3. Call generate_ict_trades() with the param override dict
      4. Classify each of the 3 trade outcomes against the next forward_bars

    Returns a flat list of result records (3 × number of evaluation points).
    """
    results = []
    indices = range(daily_lookback, len(daily_df) - forward_bars, step_bars)

    for t in indices:
        as_of   = daily_df.index[t]
        d, w, m = slice_data_as_of(daily_df, weekly_df, monthly_df,
                                    as_of, daily_lookback)
        if d.empty or w.empty or m.empty:
            continue

        bias   = calc_rolling_bias(w, as_of)
        trades = ict_analysis.generate_ict_trades(m, w, d, bias, params)
        fwd    = daily_df.iloc[t + 1 : t + 1 + forward_bars]

        for trade in trades:
            outcome = classify_outcome(trade, fwd, forward_bars)
            results.append({
                "date":         as_of,
                "trade_id":     trade.get("id"),
                "direction":    trade.get("direction"),
                "setup_name":   trade.get("setup_name", ""),
                "confidence":   trade.get("confidence"),
                "entry":        trade.get("entry"),
                "stop":         trade.get("stop"),
                "target1":      trade.get("target1"),
                "target2":      trade.get("target2"),
                "rr1":          trade.get("rr1"),
                "rr2":          trade.get("rr2"),
                "bias_score":   bias,
                **outcome,
            })

    return results


# =============================================================================
# Section 4 — Aggregate Metrics
# =============================================================================

def compute_metrics(results: list[dict]) -> dict:
    """
    Aggregate a list of result records into performance metrics.

    WAIT trades are excluded from all rate calculations.
    NO_ENTRY and EXPIRED are counted separately from triggered trades.
    """
    if not results:
        return {}

    non_wait   = [r for r in results if r["outcome"] != "WAIT"]
    triggered  = [r for r in non_wait if r["outcome"] not in ("NO_ENTRY",)]
    closed     = [r for r in triggered if r["outcome"] in ("TP1", "TP2", "SL")]
    wins_tp1   = [r for r in closed if r["outcome"] in ("TP1", "TP2")]
    wins_tp2   = [r for r in closed if r["outcome"] == "TP2"]
    losses     = [r for r in closed if r["outcome"] == "SL"]

    n_signals  = len(non_wait)
    n_trig     = len(triggered)
    n_closed   = len(closed)

    tp1_rate   = len(wins_tp1) / n_closed if n_closed else 0.0
    tp2_rate   = len(wins_tp2) / n_closed if n_closed else 0.0
    sl_rate    = len(losses)   / n_closed if n_closed else 0.0

    rr_vals    = [r["rr_achieved"] for r in closed if r["rr_achieved"] is not None]
    avg_rr     = float(np.mean(rr_vals)) if rr_vals else 0.0

    # Expectancy: E[R] per closed trade = avg_rr on wins * tp1_rate − sl_rate
    win_rr     = [r["rr_achieved"] for r in wins_tp1 if r["rr_achieved"] is not None]
    avg_win_rr = float(np.mean(win_rr)) if win_rr else 0.0
    expectancy = round(tp1_rate * avg_win_rr - sl_rate * 1.0, 4)

    def _group(subset: list[dict]) -> dict:
        """Compute sub-metrics for a filtered subset."""
        sub_closed = [r for r in subset if r["outcome"] in ("TP1", "TP2", "SL")]
        sub_n      = len(sub_closed)
        if sub_n == 0:
            return {"n": 0, "tp1_rate": 0, "tp2_rate": 0,
                    "sl_rate": 0, "avg_rr": 0, "expectancy": 0}
        s_tp1 = [r for r in sub_closed if r["outcome"] in ("TP1", "TP2")]
        s_tp2 = [r for r in sub_closed if r["outcome"] == "TP2"]
        s_sl  = [r for r in sub_closed if r["outcome"] == "SL"]
        s_tp1_rate = len(s_tp1) / sub_n
        s_sl_rate  = len(s_sl)  / sub_n
        s_win_rr   = [r["rr_achieved"] for r in s_tp1 if r["rr_achieved"] is not None]
        s_avg_win  = float(np.mean(s_win_rr)) if s_win_rr else 0.0
        s_exp      = round(s_tp1_rate * s_avg_win - s_sl_rate, 4)
        return {
            "n":          sub_n,
            "tp1_rate":   round(s_tp1_rate, 4),
            "tp2_rate":   round(len(s_tp2) / sub_n, 4),
            "sl_rate":    round(s_sl_rate,  4),
            "avg_rr":     round(float(np.mean([r["rr_achieved"] for r in sub_closed
                                               if r["rr_achieved"] is not None]
                                             ) if any(r["rr_achieved"] is not None
                                                      for r in sub_closed) else [0]), 4),
            "expectancy": s_exp,
        }

    by_trade_id  = {i: _group([r for r in non_wait if r["trade_id"] == i])
                    for i in (1, 2, 3)}
    by_confidence = {c: _group([r for r in non_wait if r["confidence"] == c])
                     for c in ("HIGH", "MEDIUM", "LOW")}

    return {
        "total_signals":    n_signals,
        "no_entry_count":   len([r for r in non_wait if r["outcome"] == "NO_ENTRY"]),
        "triggered_count":  n_trig,
        "closed_count":     n_closed,
        "tp1_win_rate":     round(tp1_rate,  4),
        "tp2_win_rate":     round(tp2_rate,  4),
        "sl_rate":          round(sl_rate,   4),
        "avg_rr_achieved":  round(avg_rr,    4),
        "expectancy":       expectancy,
        "avg_bars_held":    round(float(np.mean([r["bars_held"] for r in closed
                                                 if r["bars_held"] is not None]
                                               ) if closed else 0), 1),
        "by_trade_id":      by_trade_id,
        "by_confidence":    by_confidence,
    }


# =============================================================================
# Section 5 — Parameter Grid Search
# =============================================================================

# Key parameters for optimization (most impactful on trade quality)
_PARAM_GRID_DEF: dict[str, list] = {
    "ICT_SWING_ORDER":          [2, 3, 4],
    "ICT_OB_MIN_IMPULSE":       [0.3, 0.5, 0.8],
    "ICT_OTE_PAIR":             [
        (0.618, 0.705),   # ICT standard
        (0.600, 0.720),   # wider zone (more triggers)
        (0.628, 0.695),   # tighter zone (higher precision)
    ],
    "ICT_BIAS_BULL_THRESHOLD":  [0.05, 0.10, 0.20],
    "ICT_OTE_ATR_MULTIPLIER":   [1.0, 1.5, 2.0],    # Trade 2 stop width
    "ICT_LIQ_ATR_MULTIPLIER":   [0.75, 1.0, 1.5],   # Trade 3 stop width
}


def build_param_grid(grid_def: dict | None = None) -> list[dict]:
    """
    Expand the parameter grid definition into a flat list of param dicts.
    ICT_OTE_PAIR is unpacked into ICT_OTE_LOW / ICT_OTE_HIGH.
    ICT_BIAS_BEAR_THRESHOLD is set symmetrically (negative of bull threshold).
    """
    gd = grid_def or _PARAM_GRID_DEF
    keys   = list(gd.keys())
    combos = list(itertools.product(*[gd[k] for k in keys]))

    param_list = []
    for combo in combos:
        p: dict = dict(zip(keys, combo))
        # Unpack paired parameters
        if "ICT_OTE_PAIR" in p:
            ote_pair = p.pop("ICT_OTE_PAIR")
            p["ICT_OTE_LOW"]  = ote_pair[0]
            p["ICT_OTE_HIGH"] = ote_pair[1]
        if "ICT_BIAS_BULL_THRESHOLD" in p:
            p["ICT_BIAS_BEAR_THRESHOLD"] = -p["ICT_BIAS_BULL_THRESHOLD"]
        param_list.append(p)

    return param_list


def run_grid_search(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    param_grid: list[dict] | None = None,
    step_bars: int = 5,
    forward_bars: int = 30,
    daily_lookback: int = 120,
    verbose: bool = True,
) -> list[dict]:
    """
    Run run_single_backtest() for each param set in the grid.
    Returns a list of dicts sorted by expectancy (descending).
    """
    grid = param_grid or build_param_grid()
    n    = len(grid)
    if verbose:
        print(f"\nRunning grid search: {n} combinations …", flush=True)

    ranked = []
    for i, params in enumerate(grid, 1):
        if verbose and (i % 20 == 0 or i == n):
            print(f"  [{i:>3}/{n}] …", flush=True)
        results  = run_single_backtest(daily_df, weekly_df, monthly_df,
                                       params, step_bars, forward_bars, daily_lookback)
        metrics  = compute_metrics(results)
        exp      = metrics.get("expectancy", -99.0)
        ranked.append({"params": params, "metrics": metrics, "expectancy": exp})

    ranked.sort(key=lambda x: x["expectancy"], reverse=True)
    return ranked


# =============================================================================
# Section 6 — Terminal Output
# =============================================================================

def _pct(v: float) -> str:
    return f"{v * 100:>5.1f}%"


def _fmt(v, precision: int = 3) -> str:
    if v is None:
        return "   N/A"
    return f"{v:>{precision + 4}.{precision}f}"


def print_metrics_table(metrics: dict, params: dict | None = None,
                        label: str = "BACKTEST RESULTS") -> None:
    """Print a formatted terminal table for a single backtest result."""
    SEP = "=" * 62
    print(f"\n{SEP}")
    print(f"  {label}")
    if params:
        p_str = "  Params: " + ", ".join(
            f"{k.replace('ICT_','').lower()}={v}" for k, v in params.items()
        )
        print(p_str[:60])
    print(SEP)
    m = metrics
    print(f"  Total signals      : {m.get('total_signals', 0):>5}")
    print(f"  No entry           : {m.get('no_entry_count', 0):>5}  "
          f"  Triggered  : {m.get('triggered_count', 0):>5}")
    print(f"  Closed trades      : {m.get('closed_count', 0):>5}")
    print(f"  -- Triggered trade outcomes ----------------------------------")
    print(f"  TP1 win rate       : {_pct(m.get('tp1_win_rate', 0))}")
    print(f"  TP2 win rate       : {_pct(m.get('tp2_win_rate', 0))}")
    print(f"  SL rate            : {_pct(m.get('sl_rate', 0))}")
    print(f"  Avg RR achieved    : {_fmt(m.get('avg_rr_achieved', 0))}")
    print(f"  Expectancy E[R]    : {_fmt(m.get('expectancy', 0))}")
    print(f"  Avg bars held      : {m.get('avg_bars_held', 0):>5.1f}")
    print(f"  -- By Trade ID -----------------------------------------------")
    for tid, sub in m.get("by_trade_id", {}).items():
        print(f"  Trade {tid}  n={sub['n']:>3}  "
              f"TP1:{_pct(sub['tp1_rate'])}  SL:{_pct(sub['sl_rate'])}  "
              f"E:{_fmt(sub['expectancy'])}")
    print(f"  -- By Confidence ---------------------------------------------")
    for conf, sub in m.get("by_confidence", {}).items():
        print(f"  {conf:<6}  n={sub['n']:>3}  "
              f"TP1:{_pct(sub['tp1_rate'])}  SL:{_pct(sub['sl_rate'])}  "
              f"E:{_fmt(sub['expectancy'])}")
    print(SEP)


def print_ranked_results(ranked: list[dict], top_n: int = 10) -> None:
    """Print a ranked table of the top N grid search results."""
    print(f"\n{'=' * 84}")
    print(f"  GRID SEARCH — Top {top_n} results (ranked by Expectancy)")
    print(f"{'=' * 84}")
    hdr = (f"{'Rank':>4}  {'Expect':>7}  {'TP1%':>5}  {'SL%':>5}  "
           f"{'AvgRR':>6}  {'SwOrd':>5}  {'OBImp':>5}  "
           f"{'OTE':>11}  {'BiasThr':>7}")
    print(hdr)
    print("-" * 84)
    for i, rec in enumerate(ranked[:top_n], 1):
        m = rec["metrics"]
        p = rec["params"]
        ote_str = f"{p.get('ICT_OTE_LOW',0):.3f}/{p.get('ICT_OTE_HIGH',0):.3f}"
        row = (f"{i:>4}  {rec['expectancy']:>+7.4f}  "
               f"{_pct(m.get('tp1_win_rate',0)):>5}  "
               f"{_pct(m.get('sl_rate',0)):>5}  "
               f"{m.get('avg_rr_achieved',0):>6.3f}  "
               f"{p.get('ICT_SWING_ORDER','—'):>5}  "
               f"{p.get('ICT_OB_MIN_IMPULSE','—'):>5}  "
               f"{ote_str:>11}  "
               f"{p.get('ICT_BIAS_BULL_THRESHOLD','—'):>7}")
        print(row)
    print("=" * 84)


def print_optimal_params(ranked: list[dict]) -> None:
    """Print the best param set and compare to config defaults."""
    if not ranked:
        print("No ranked results to display.")
        return
    best = ranked[0]
    print(f"\n{'=' * 62}")
    print("  OPTIMAL PARAMETERS vs CONFIG DEFAULTS")
    print(f"  Expectancy improvement: baseline -> {best['expectancy']:+.4f}")
    print(f"{'=' * 62}")
    defaults = {
        "ICT_SWING_ORDER":         config.ICT_SWING_ORDER,
        "ICT_OB_MIN_IMPULSE":      config.ICT_OB_MIN_IMPULSE,
        "ICT_OTE_LOW":             config.ICT_OTE_LOW,
        "ICT_OTE_HIGH":            config.ICT_OTE_HIGH,
        "ICT_BIAS_BULL_THRESHOLD": config.ICT_BIAS_BULL_THRESHOLD,
        "ICT_OTE_ATR_MULTIPLIER":  config.ICT_OTE_ATR_MULTIPLIER,
        "ICT_LIQ_ATR_MULTIPLIER":  config.ICT_LIQ_ATR_MULTIPLIER,
    }
    print(f"  {'Parameter':<28}  {'Default':>8}  {'Optimal':>8}  Delta")
    print("  " + "-" * 58)
    for key, default_val in defaults.items():
        opt_val = best["params"].get(key, default_val)
        delta   = (f"{opt_val - default_val:+.3f}"
                   if isinstance(opt_val, (int, float)) else "—")
        changed = "  <--" if opt_val != default_val else ""
        print(f"  {key.replace('ICT_',''):<28}  {str(default_val):>8}  "
              f"{str(opt_val):>8}  {delta}{changed}")
    print(f"{'=' * 62}")
    print("\n  To apply: update config.py with the optimal values above.")


# =============================================================================
# Section 7 — Main Entry Points
# =============================================================================

def run_baseline(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    step_bars: int = 5,
    forward_bars: int = 30,
    daily_lookback: int = 120,
) -> dict:
    """Run backtest with config.py defaults and print results. Returns metrics."""
    print("\nRunning baseline backtest (config.py defaults) …", flush=True)
    results = run_single_backtest(daily_df, weekly_df, monthly_df,
                                  params=None,
                                  step_bars=step_bars,
                                  forward_bars=forward_bars,
                                  daily_lookback=daily_lookback)
    metrics = compute_metrics(results)
    print_metrics_table(metrics, label="BASELINE — config.py defaults")
    return metrics


def main() -> None:
    """CLI entry point."""
    baseline_only = "--baseline" in sys.argv or "--baseline-only" in sys.argv

    daily_df, weekly_df, monthly_df = fetch_backtest_data()

    baseline_metrics = run_baseline(daily_df, weekly_df, monthly_df)

    if baseline_only:
        print("\nBaseline-only mode. Skipping grid search.")
        return

    grid    = build_param_grid()
    ranked  = run_grid_search(daily_df, weekly_df, monthly_df, grid)

    print_ranked_results(ranked, top_n=10)
    print_optimal_params(ranked)

    # Annotate baseline rank
    base_exp = baseline_metrics.get("expectancy", 0.0)
    base_rank = next(
        (i for i, r in enumerate(ranked, 1) if abs(r["expectancy"] - base_exp) < 1e-6),
        None,
    )
    if base_rank:
        print(f"\n  Baseline (config defaults) ranked #{base_rank} of {len(ranked)}.")


if __name__ == "__main__":
    main()
