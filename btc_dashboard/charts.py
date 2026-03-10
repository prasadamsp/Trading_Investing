# =============================================================================
# Bitcoin Weekly Bias Dashboard — Chart Builders (Plotly)
# =============================================================================
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config

# Common theme colours — BTC uses orange accent instead of gold
BULL_COLOR    = "#00C853"
BEAR_COLOR    = "#D50000"
NEUTRAL_COLOR = "#FFD740"
BTC_COLOR     = "#F7931A"     # Official Bitcoin orange


def _hex_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB hex + alpha float → 'rgba(r,g,b,a)' for Plotly compatibility."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
ETH_COLOR     = "#627EEA"     # Ethereum purple-blue
BG_COLOR      = "#0E1117"
GRID_COLOR    = "#1E2129"
TEXT_COLOR    = "#FAFAFA"

_LAYOUT = dict(
    paper_bgcolor=BG_COLOR,
    plot_bgcolor=BG_COLOR,
    font=dict(color=TEXT_COLOR, family="Inter, Arial, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    xaxis=dict(gridcolor=GRID_COLOR, zeroline=False),
    yaxis=dict(gridcolor=GRID_COLOR, zeroline=False),
)


def _apply_layout(fig, **extra) -> go.Figure:
    fig.update_layout(**{**_LAYOUT, **extra})
    return fig


# ---------------------------------------------------------------------------
# BTC Price + Moving Averages
# ---------------------------------------------------------------------------

def chart_btc_price_ma(prices: dict, ma_data: dict) -> go.Figure:
    """Weekly BTC price chart with MA overlays."""
    btc = prices.get("btc", pd.DataFrame()).get("Close", pd.Series())
    if btc.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=btc.index, y=btc.values,
        name="BTC-USD", line=dict(color=BTC_COLOR, width=2),
    ))

    colors = {20: "#40C4FF", 50: "#FF6D00", 200: "#CE93D8"}
    for p in ma_data:
        ma_series = btc.rolling(p).mean()
        fig.add_trace(go.Scatter(
            x=ma_series.index, y=ma_series.values,
            name=f"{p}W MA", line=dict(color=colors.get(p, "#888"), width=1.2, dash="dot"),
        ))

    _apply_layout(fig, title="Bitcoin Price — Weekly + MAs", height=350,
                  yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$"))
    return fig


# ---------------------------------------------------------------------------
# RSI Chart
# ---------------------------------------------------------------------------

def chart_rsi(prices: dict) -> go.Figure:
    """Weekly RSI for BTC."""
    import numpy as np
    btc = prices.get("btc", pd.DataFrame()).get("Close", pd.Series())
    if btc.empty:
        return go.Figure()

    delta = btc.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rsi_series.index, y=rsi_series.values,
        name="RSI (14)", line=dict(color="#40C4FF", width=1.8),
        fill="tozeroy", fillcolor="rgba(64,196,255,0.08)",
    ))
    for level, color, label in [(70, BEAR_COLOR, "OB 70"), (50, NEUTRAL_COLOR, "50"), (30, BULL_COLOR, "OS 30")]:
        fig.add_hline(y=level, line=dict(color=color, dash="dot", width=1),
                      annotation_text=label, annotation_position="right")

    _apply_layout(fig, title="RSI (14) — Weekly", height=200,
                  yaxis=dict(range=[0, 100], gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# MACD Chart
# ---------------------------------------------------------------------------

def chart_macd(prices: dict) -> go.Figure:
    """Weekly MACD for BTC."""
    btc = prices.get("btc", pd.DataFrame()).get("Close", pd.Series())
    if btc.empty:
        return go.Figure()

    ema_fast    = btc.ewm(span=config.MACD_FAST,   adjust=False).mean()
    ema_slow    = btc.ewm(span=config.MACD_SLOW,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=config.MACD_SIGNAL, adjust=False).mean()
    histogram   = macd_line - signal_line

    bar_colors = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in histogram.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=histogram.index, y=histogram.values,
        name="Histogram", marker_color=bar_colors, opacity=0.7,
    ))
    fig.add_trace(go.Scatter(
        x=macd_line.index, y=macd_line.values,
        name="MACD", line=dict(color="#40C4FF", width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=signal_line.index, y=signal_line.values,
        name="Signal", line=dict(color=NEUTRAL_COLOR, width=1.2, dash="dot"),
    ))
    fig.add_hline(y=0, line=dict(color="#555", width=1))

    _apply_layout(fig, title="MACD — Weekly", height=220)
    return fig


# ---------------------------------------------------------------------------
# Fear & Greed Index Chart
# ---------------------------------------------------------------------------

def chart_fear_greed(fg_df: pd.DataFrame) -> go.Figure:
    """Time series of Crypto Fear & Greed Index with threshold zones."""
    if fg_df.empty or "value" not in fg_df.columns:
        fig = go.Figure()
        fig.add_annotation(text="Fear & Greed data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="Crypto Fear & Greed Index", height=250)
        return fig

    vals = fg_df["value"].dropna().tail(365)  # last year of daily data
    bar_colors = []
    for v in vals.values:
        if v < 20:
            bar_colors.append(BULL_COLOR)       # extreme fear = buy zone
        elif v < 40:
            bar_colors.append("#69F0AE")        # fear
        elif v <= 60:
            bar_colors.append(NEUTRAL_COLOR)    # neutral
        elif v <= 80:
            bar_colors.append("#FF6D00")        # greed
        else:
            bar_colors.append(BEAR_COLOR)       # extreme greed = sell zone

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=vals.index, y=vals.values,
        marker_color=bar_colors, opacity=0.85,
        name="Fear & Greed",
    ))
    # Zone lines
    for level, color, label in [
        (80, BEAR_COLOR,    "Extreme Greed"),
        (60, "#FF6D00",     "Greed"),
        (40, NEUTRAL_COLOR, "Fear"),
        (20, BULL_COLOR,    "Extreme Fear"),
    ]:
        fig.add_hline(y=level, line=dict(color=color, dash="dot", width=1),
                      annotation_text=label, annotation_position="right",
                      annotation_font=dict(size=9, color=color))

    _apply_layout(fig, title="Crypto Fear & Greed Index (Daily) — Extreme Fear=Buy · Extreme Greed=Sell",
                  height=280, yaxis=dict(range=[0, 100], gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# COT Chart
# ---------------------------------------------------------------------------

def chart_cot(cot_df: pd.DataFrame) -> go.Figure:
    """CME Bitcoin futures COT — managed money net positions."""
    if cot_df.empty or "noncomm_net" not in cot_df.columns:
        fig = go.Figure()
        fig.add_annotation(text="COT data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="COT — Managed Money Net Positions (CME Bitcoin Futures)", height=250)
        return fig

    net = cot_df["noncomm_net"].dropna()
    bar_colors = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in net.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=net.index, y=net.values,
        name="Net Spec Long", marker_color=bar_colors, opacity=0.8,
    ))
    fig.add_hline(y=0, line=dict(color="#555", width=1))

    _apply_layout(fig, title="COT — Managed Money Net Positions (CME Bitcoin Futures)", height=250)
    return fig


# ---------------------------------------------------------------------------
# BTC ETF Flows Bar Chart
# ---------------------------------------------------------------------------

def chart_etf_flows(etf_data: dict) -> go.Figure:
    """Weekly % change for all 6 BTC spot ETFs."""
    etf_keys = ["ibit", "fbtc", "gbtc", "arkb", "hodl", "bitb"]
    labels   = ["IBIT", "FBTC", "GBTC", "ARKB", "HODL", "BITB"]
    values   = [etf_data.get(k, {}).get("weekly_chg_pct", 0) or 0 for k in etf_keys]
    colors   = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in values]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors, opacity=0.85,
        text=[f"{v:+.2f}%" for v in values],
        textposition="outside",
    ))
    fig.add_hline(y=0, line=dict(color="#555", width=1))
    _apply_layout(fig, title="Bitcoin Spot ETFs — Weekly Price Change %", height=280,
                  yaxis=dict(gridcolor=GRID_COLOR, zeroline=False, ticksuffix="%"))
    return fig


# ---------------------------------------------------------------------------
# DXY Chart
# ---------------------------------------------------------------------------

def chart_dxy(prices: dict) -> go.Figure:
    """DXY weekly — key macro driver for BTC."""
    dxy = prices.get("dxy", pd.DataFrame()).get("Close", pd.Series())
    if dxy.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dxy.index, y=dxy.values,
        name="DXY", line=dict(color="#FF6D00", width=2),
        fill="tozeroy", fillcolor="rgba(255,109,0,0.07)",
    ))
    _apply_layout(fig, title="US Dollar Index (DXY) — Weekly", height=260)
    return fig


# ---------------------------------------------------------------------------
# Real Yield & Breakeven Chart
# ---------------------------------------------------------------------------

def chart_real_yield(fred: dict) -> go.Figure:
    """10Y real yield and breakeven inflation — key macro context for BTC."""
    ry = fred.get("real_yield_10y", pd.Series())
    be = fred.get("breakeven_10y", pd.Series())

    fig = go.Figure()
    if not ry.empty:
        fig.add_trace(go.Scatter(x=ry.index, y=ry.values, name="10Y Real Yield",
                                 line=dict(color="#CE93D8", width=2)))
    if not be.empty:
        fig.add_trace(go.Scatter(x=be.index, y=be.values, name="10Y Breakeven Inflation",
                                 line=dict(color=NEUTRAL_COLOR, width=1.5, dash="dot")))
    fig.add_hline(y=0, line=dict(color=BEAR_COLOR, dash="dot", width=1),
                  annotation_text="0% (real rate threshold)", annotation_position="right")

    _apply_layout(fig, title="10Y Real Yield & Breakeven Inflation", height=280,
                  yaxis=dict(ticksuffix="%", gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# Yield Curve Chart
# ---------------------------------------------------------------------------

def chart_yield_curve(fred: dict) -> go.Figure:
    """10Y-2Y yield curve spread."""
    def _safe_resample(s: pd.Series) -> pd.Series:
        if s.empty or not isinstance(s.index, pd.DatetimeIndex):
            return pd.Series(dtype=float)
        return s.resample("W").last()

    t2  = _safe_resample(fred.get("treasury_2y",  pd.Series()))
    t10 = _safe_resample(fred.get("treasury_10y", pd.Series()))

    if t2.empty or t10.empty:
        fig = go.Figure()
        _apply_layout(fig, title="Yield Curve (10Y-2Y)", height=220)
        return fig

    spread = (t10 - t2).dropna()
    bar_colors = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in spread.values]

    fig = go.Figure(go.Bar(x=spread.index, y=spread.values,
                           marker_color=bar_colors, opacity=0.8, name="10Y-2Y Spread"))
    fig.add_hline(y=0, line=dict(color="#555", width=1.5))
    _apply_layout(fig, title="Yield Curve — 10Y minus 2Y Spread (%)", height=220,
                  yaxis=dict(ticksuffix="%", gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# Cross-asset overview (BTC-specific)
# ---------------------------------------------------------------------------

def chart_cross_asset(prices: dict) -> go.Figure:
    """BTC cross-asset context: VIX, SPX, QQQ, ETH, DXY."""
    assets = {
        "VIX":     prices.get("vix",    pd.DataFrame()).get("Close", pd.Series()),
        "S&P 500": prices.get("spx",    pd.DataFrame()).get("Close", pd.Series()),
        "QQQ":     prices.get("qqq",    pd.DataFrame()).get("Close", pd.Series()),
        "ETH":     prices.get("eth",    pd.DataFrame()).get("Close", pd.Series()),
        "EUR/USD": prices.get("eurusd", pd.DataFrame()).get("Close", pd.Series()),
    }

    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=list(assets.keys()),
        vertical_spacing=0.10,
        horizontal_spacing=0.06,
    )
    colors = ["#FF6D00", "#40C4FF", "#00C853", ETH_COLOR, "#CE93D8"]
    positions = [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1)]

    for (name, series), color, (row, col) in zip(assets.items(), colors, positions):
        if series.empty:
            continue
        fig.add_trace(
            go.Scatter(x=series.index, y=series.values, name=name,
                       line=dict(color=color, width=1.5)),
            row=row, col=col,
        )

    _apply_layout(fig, title="Cross-Asset — Weekly", height=550)
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)
    return fig


# ---------------------------------------------------------------------------
# BTC vs ETH relative performance chart
# ---------------------------------------------------------------------------

def chart_btc_eth_ratio(prices: dict) -> go.Figure:
    """BTC/ETH ratio over time — BTC dominance proxy."""
    btc = prices.get("btc", pd.DataFrame()).get("Close", pd.Series())
    eth = prices.get("eth", pd.DataFrame()).get("Close", pd.Series())

    if btc.empty or eth.empty:
        return go.Figure()

    ratio = (btc / eth).dropna()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ratio.index, y=ratio.values,
        name="BTC/ETH", line=dict(color=BTC_COLOR, width=2),
        fill="tozeroy", fillcolor=f"rgba(247,147,26,0.07)",
    ))
    _apply_layout(fig, title="BTC / ETH Ratio — BTC Dominance Proxy", height=240)
    return fig


# ---------------------------------------------------------------------------
# Bias Gauge (speedometer-style)
# ---------------------------------------------------------------------------

def chart_bias_gauge(score: float, label: str, color: str) -> go.Figure:
    """Speedometer gauge showing the overall BTC bias score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score * 100,
        number={"suffix": "", "font": {"size": 28, "color": color}},
        gauge={
            "axis": {"range": [-100, 100], "tickwidth": 1, "tickcolor": TEXT_COLOR},
            "bar":  {"color": color, "thickness": 0.3},
            "bgcolor": BG_COLOR,
            "borderwidth": 0,
            "steps": [
                {"range": [-100, -60], "color": "#D50000"},
                {"range": [-60,  -20], "color": "#FF6D00"},
                {"range": [-20,   20], "color": "#FFD740"},
                {"range": [ 20,   60], "color": "#69F0AE"},
                {"range": [ 60,  100], "color": "#00C853"},
            ],
            "threshold": {"line": {"color": "white", "width": 3},
                          "thickness": 0.8, "value": score * 100},
        },
        title={"text": label, "font": {"size": 20, "color": color}},
    ))
    _apply_layout(fig, height=260, margin=dict(l=20, r=20, t=40, b=20))
    return fig


# ---------------------------------------------------------------------------
# Score breakdown bar chart
# ---------------------------------------------------------------------------

def chart_score_breakdown(group_scores: dict, breakdown: dict) -> go.Figure:
    """Horizontal bar chart of bias scores by group."""
    groups = list(group_scores.keys())
    scores = [group_scores[g] for g in groups]
    colors = [BULL_COLOR if s > 0 else (BEAR_COLOR if s < 0 else NEUTRAL_COLOR) for s in scores]

    fig = go.Figure(go.Bar(
        y=[g.replace("_", " ").title() for g in groups],
        x=scores,
        orientation="h",
        marker_color=colors,
        opacity=0.85,
        text=[f"{s:+.2f}" for s in scores],
        textposition="outside",
    ))
    fig.add_vline(x=0, line=dict(color="#555", width=1.5))
    _apply_layout(fig, title="Bias Score by Group", height=220,
                  xaxis=dict(range=[-1, 1], gridcolor=GRID_COLOR),
                  yaxis=dict(gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# BTC Halving Cycle Chart
# ---------------------------------------------------------------------------

def chart_halving_cycle(halving: dict) -> go.Figure:
    """
    Visual progress bar of the current BTC halving cycle with phase annotations.
    Shows: last halving → current position → next halving.
    """
    fig = go.Figure()

    if not halving or halving.get("cycle_pct") is None:
        fig.add_annotation(text="Halving data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="BTC Halving Cycle Progress", height=160)
        return fig

    cycle_pct  = halving["cycle_pct"]
    phase      = halving["phase"]
    days_to    = halving["days_to_next"]
    last_h     = halving["last_halving"]
    next_h     = halving["next_halving"]
    months_sin = halving["months_since"]

    phase_colors = {
        "Early Bull":  BULL_COLOR,
        "Peak Risk":   "#FF6D00",
        "Bear Market": BEAR_COLOR,
        "Pre-Halving": "#FFD740",
    }
    color = phase_colors.get(phase, BTC_COLOR)

    # Phase zones as background bands (% of cycle)
    phase_bands = [
        (0,   37.5, BULL_COLOR,   0.07),   # Early Bull: 0-18m of ~48m cycle
        (37.5, 62.5, "#FF6D00",  0.07),   # Peak Risk: 18-30m
        (62.5, 87.5, BEAR_COLOR,  0.07),   # Bear: 30-42m
        (87.5, 100,  "#FFD740",   0.07),   # Pre-Halving: 42m+
    ]
    for x0, x1, fc, op in phase_bands:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0, y1=1, xref="x", yref="paper",
                      fillcolor=fc, opacity=op, line=dict(width=0), layer="below")

    # Progress bar (filled portion)
    fig.add_trace(go.Bar(
        x=[cycle_pct], y=["Cycle"],
        orientation="h",
        marker=dict(color=color, opacity=0.85),
        width=0.5,
        showlegend=False,
        text=[f"  {cycle_pct:.1f}% — {phase}  ({months_sin:.0f}m since halving)"],
        textposition="inside" if cycle_pct > 15 else "outside",
        insidetextanchor="middle",
        textfont=dict(color="#000", size=13, family="Inter, Arial, sans-serif"),
    ))

    # Phase boundary lines
    for x_pct, label in [(37.5, "18m"), (62.5, "30m"), (87.5, "42m")]:
        fig.add_shape(type="line", x0=x_pct, x1=x_pct, y0=0, y1=1,
                      xref="x", yref="paper",
                      line=dict(color="#555", dash="dot", width=1))
        fig.add_annotation(x=x_pct, y=1.05, text=label, showarrow=False,
                           xref="x", yref="paper",
                           font=dict(size=9, color="#888"), xanchor="center")

    _apply_layout(
        fig,
        title=f"₿ Halving Cycle — {last_h} → {next_h} · {days_to:,} days to next halving · Phase: {phase}",
        height=160,
        xaxis=dict(range=[0, 100], ticksuffix="%", gridcolor=GRID_COLOR, zeroline=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=50, b=30),
    )
    return fig


# ---------------------------------------------------------------------------
# On-Chain Hash Rate Chart
# ---------------------------------------------------------------------------

def chart_hashrate(onchain_snapshot: dict) -> go.Figure:
    """BTC network hash rate trend from blockchain.com."""
    hr = onchain_snapshot.get("hash_rate", {})
    series = hr.get("series")

    if series is None or (isinstance(series, pd.Series) and series.empty):
        fig = go.Figure()
        fig.add_annotation(text="Hash rate data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="BTC Network Hash Rate (EH/s)", height=220)
        return fig

    color = BULL_COLOR if hr.get("rising") else BEAR_COLOR
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values,
        name="Hash Rate (EH/s)", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=_hex_rgba(color, 0.08),
    ))
    trend_pct = hr.get("trend_pct")
    trend_str = f"4W trend: {'▲' if trend_pct and trend_pct > 0 else '▼'} {abs(trend_pct):.1f}%" if trend_pct is not None else ""
    _apply_layout(fig, title=f"BTC Network Hash Rate (EH/s) — {trend_str}", height=220,
                  yaxis=dict(gridcolor=GRID_COLOR, ticksuffix=" EH/s"))
    return fig


# ---------------------------------------------------------------------------
# Miner Revenue Chart
# ---------------------------------------------------------------------------

def chart_miner_revenue(onchain_snapshot: dict) -> go.Figure:
    """BTC miner daily revenue trend from blockchain.com."""
    mr = onchain_snapshot.get("miner_revenue", {})
    series = mr.get("series")

    if series is None or (isinstance(series, pd.Series) and series.empty):
        fig = go.Figure()
        fig.add_annotation(text="Miner revenue data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="BTC Miner Daily Revenue (USD)", height=220)
        return fig

    color = BULL_COLOR if mr.get("rising") else BEAR_COLOR
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values / 1e6,  # convert to millions
        name="Miner Revenue ($M/day)", line=dict(color=color, width=1.8),
        fill="tozeroy", fillcolor=_hex_rgba(color, 0.07),
    ))
    _apply_layout(fig, title="BTC Miner Daily Revenue ($M/day) — Rising = Healthy Network",
                  height=220, yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$", ticksuffix="M"))
    return fig


# ---------------------------------------------------------------------------
# Bollinger Bands — Weekly BTC with BB overlay
# ---------------------------------------------------------------------------

def chart_bollinger_bands(prices: dict, bb: dict) -> go.Figure:
    """Weekly BTC price with 20W Bollinger Bands (2σ) and %B sub-panel."""
    btc = prices.get("btc", pd.DataFrame()).get("Close", pd.Series())
    if btc.empty or not bb:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.04,
        subplot_titles=["BTC Price + 20W Bollinger Bands (2σ)", "%B Oscillator"],
    )

    # Price
    fig.add_trace(go.Scatter(
        x=btc.index, y=btc.values,
        name="BTC-USD", line=dict(color=BTC_COLOR, width=2),
    ), row=1, col=1)

    # Upper / Middle / Lower bands
    upper_s  = bb.get("upper_series")
    lower_s  = bb.get("lower_series")
    middle_s = bb.get("middle_series")

    if upper_s is not None and not upper_s.empty:
        fig.add_trace(go.Scatter(
            x=upper_s.index, y=upper_s.values,
            name="Upper BB", line=dict(color="#CE93D8", width=1.2, dash="dot"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=lower_s.index, y=lower_s.values,
            name="Lower BB", line=dict(color="#CE93D8", width=1.2, dash="dot"),
            fill="tonexty", fillcolor="rgba(206,147,216,0.06)",
        ), row=1, col=1)
    if middle_s is not None and not middle_s.empty:
        fig.add_trace(go.Scatter(
            x=middle_s.index, y=middle_s.values,
            name="20W MA (mid)", line=dict(color="#888888", width=1, dash="dash"),
        ), row=1, col=1)

    # %B oscillator
    if not btc.empty and upper_s is not None and lower_s is not None:
        pct_b_series = ((btc - lower_s) / (upper_s - lower_s) * 100).dropna()
        bar_colors   = [BULL_COLOR if v <= 15 else (BEAR_COLOR if v >= 85 else NEUTRAL_COLOR)
                        for v in pct_b_series.values]
        fig.add_trace(go.Bar(
            x=pct_b_series.index, y=pct_b_series.values,
            name="%B", marker_color=bar_colors, opacity=0.75,
        ), row=2, col=1)
        for lvl, color, lbl in [(100, BEAR_COLOR, "Above Upper"), (80, "#FF6D00", "Near Upper"),
                                  (50, NEUTRAL_COLOR, "Mid"),
                                  (20, "#69F0AE", "Near Lower"), (0, BULL_COLOR, "Below Lower")]:
            fig.add_hline(y=lvl, line=dict(color=color, dash="dot", width=0.8),
                          annotation_text=lbl, annotation_font=dict(size=8, color=color),
                          row=2, col=1)

    _apply_layout(fig, title="Bollinger Bands (20W, 2σ) — Squeeze / Expansion", height=400,
                  yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$"),
                  yaxis2=dict(gridcolor=GRID_COLOR, range=[-10, 110], ticksuffix="%"))
    fig.update_xaxes(gridcolor=GRID_COLOR)
    return fig


# ---------------------------------------------------------------------------
# Funding Rate Chart
# ---------------------------------------------------------------------------

def chart_funding_rate(funding_signal: dict) -> go.Figure:
    """BTC perp funding rate history — extreme positive = crowded longs (bearish)."""
    series = funding_signal.get("series")
    if series is None or (isinstance(series, pd.DataFrame) and series.empty):
        fig = go.Figure()
        fig.add_annotation(text="Funding rate data unavailable (OKX API)",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="BTC Perp Funding Rate (8h)", height=250)
        return fig

    rates = series["rate"].dropna() if "rate" in series.columns else pd.Series()
    bar_colors = []
    for v in rates.values:
        if v > 0.05:
            bar_colors.append(BEAR_COLOR)       # extreme long (bearish)
        elif v > 0:
            bar_colors.append("#FF6D00")        # mild long
        elif v < -0.01:
            bar_colors.append(BULL_COLOR)       # shorts crowded (bullish)
        else:
            bar_colors.append(NEUTRAL_COLOR)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=rates.index, y=rates.values,
        name="Funding Rate (%/8h)", marker_color=bar_colors, opacity=0.85,
    ))
    fig.add_hline(y=0.05, line=dict(color=BEAR_COLOR, dash="dot", width=1),
                  annotation_text="Extreme Long (0.05%)", annotation_position="right",
                  annotation_font=dict(size=9, color=BEAR_COLOR))
    fig.add_hline(y=-0.01, line=dict(color=BULL_COLOR, dash="dot", width=1),
                  annotation_text="Extreme Short (-0.01%)", annotation_position="right",
                  annotation_font=dict(size=9, color=BULL_COLOR))
    fig.add_hline(y=0, line=dict(color="#555", width=1))

    _apply_layout(fig, title="BTC/USDT Perp Funding Rate (8h) — Source: OKX",
                  height=260, yaxis=dict(gridcolor=GRID_COLOR, ticksuffix="%"))
    return fig


# ---------------------------------------------------------------------------
# Open Interest Chart
# ---------------------------------------------------------------------------

def chart_open_interest(oi_signal: dict, prices: dict) -> go.Figure:
    """BTC perp open interest vs price — detect trend confirmation vs divergence."""
    oi_df = oi_signal.get("series")
    if oi_df is None or (isinstance(oi_df, pd.DataFrame) and oi_df.empty):
        fig = go.Figure()
        fig.add_annotation(text="Open interest data unavailable (OKX API)",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="BTC Perp Open Interest", height=250)
        return fig

    btc_close = prices.get("btc", pd.DataFrame()).get("Close", pd.Series()).dropna()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.45],
        vertical_spacing=0.04,
        subplot_titles=["BTC Price (Weekly)", "Open Interest ($B) — 30 Days"],
    )

    # Price (weekly)
    if not btc_close.empty:
        fig.add_trace(go.Scatter(
            x=btc_close.index, y=btc_close.values,
            name="BTC-USD", line=dict(color=BTC_COLOR, width=2),
        ), row=1, col=1)

    # OI bars
    if "oi_usd" in oi_df.columns:
        oi_vals = oi_df["oi_usd"] / 1e9   # to billions
        oi_color = BULL_COLOR if oi_signal.get("oi_rising") else BEAR_COLOR
        fig.add_trace(go.Bar(
            x=oi_vals.index, y=oi_vals.values,
            name="OI ($B)", marker_color=oi_color, opacity=0.75,
        ), row=2, col=1)

    regime_label = {
        "confirmed_bull":      "OI ↑ + Price ↑ = Confirmed Bull",
        "bearish_distribution": "OI ↑ + Price ↓ = Bearish Distribution",
        "short_covering":       "OI ↓ + Price ↑ = Short Covering / Weak",
        "bearish_liquidation":  "OI ↓ + Price ↓ = Bearish Liquidation",
    }.get(oi_signal.get("regime", ""), "")

    _apply_layout(fig, title=f"Open Interest vs Price — {regime_label}", height=360,
                  yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$"),
                  yaxis2=dict(gridcolor=GRID_COLOR, tickprefix="$", ticksuffix="B"))
    fig.update_xaxes(gridcolor=GRID_COLOR)
    return fig


# ---------------------------------------------------------------------------
# Key Price Levels — Horizontal distance chart
# ---------------------------------------------------------------------------

def chart_key_levels_distance(key_levels: dict) -> go.Figure:
    """
    Horizontal bar chart showing BTC's distance from key price levels
    (ATH, 52W H/L, psychological levels nearest above/below).
    """
    if not key_levels:
        return go.Figure()

    current = key_levels.get("current_price", 0)
    levels  = []

    # ATH
    if key_levels.get("ath"):
        levels.append(("ATH", key_levels["ath"], key_levels.get("ath_dist_pct", 0)))
    # 52W High / Low
    if key_levels.get("w52_high"):
        levels.append(("52W High", key_levels["w52_high"], key_levels.get("w52_high_dist", 0)))
    if key_levels.get("w52_low"):
        levels.append(("52W Low",  key_levels["w52_low"],  key_levels.get("w52_low_dist", 0)))

    # Nearest psychological levels
    for item in key_levels.get("nearest_above", []):
        levels.append((f"${item['level']:,}", item["level"], item["dist_pct"]))
    for item in key_levels.get("nearest_below", []):
        levels.append((f"${item['level']:,}", item["level"], item["dist_pct"]))

    # Sort by price descending
    levels.sort(key=lambda x: x[1], reverse=True)

    labels    = [l[0] for l in levels]
    distances = [l[2] for l in levels]
    prices    = [l[1] for l in levels]
    colors    = [BULL_COLOR if d > 0 else BEAR_COLOR for d in distances]

    fig = go.Figure(go.Bar(
        y=labels,
        x=distances,
        orientation="h",
        marker_color=colors,
        opacity=0.8,
        text=[f"${p:,.0f}  ({d:+.1f}%)" for p, d in zip(prices, distances)],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig.add_vline(x=0, line=dict(color=BTC_COLOR, width=2),
                  annotation_text=f"Current ${current:,.0f}",
                  annotation_position="top",
                  annotation_font=dict(color=BTC_COLOR, size=11))
    _apply_layout(fig,
                  title="Key Price Levels — Distance from Current BTC Price",
                  height=350,
                  xaxis=dict(gridcolor=GRID_COLOR, ticksuffix="%", zeroline=False),
                  yaxis=dict(gridcolor=GRID_COLOR),
                  margin=dict(l=80, r=140, t=50, b=10))
    return fig


# ---------------------------------------------------------------------------
# ICT Levels Chart — Daily candlestick with FVG/OB/Fibonacci overlays
# ---------------------------------------------------------------------------

def chart_ict_levels(daily_df, weekly_df, trades: list, key_levels: dict,
                     fvgs: list, obs: list, fib: dict) -> go.Figure:
    """
    Daily candlestick chart for BTC with ICT overlays:
      - Shaded Fair Value Gap zones (bullish = blue, bearish = orange)
      - Shaded Order Block zones   (bullish = green, bearish = red)
      - Fibonacci level lines
      - Key level lines (PWH, PWL, PMH, PML, CMH, CML)
      - Trade entry / stop / target levels for all 3 trades
    """
    if daily_df is None or daily_df.empty or "High" not in daily_df.columns:
        fig = go.Figure()
        fig.add_annotation(text="ICT chart data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="ICT Levels — Daily Bitcoin (BTC-USD)", height=550)
        return fig

    # ── 1. Candlestick base ───────────────────────────────────────────────
    fig = go.Figure(data=[go.Candlestick(
        x=daily_df.index,
        open=daily_df["Open"],
        high=daily_df["High"],
        low=daily_df["Low"],
        close=daily_df["Close"],
        name="BTC (Daily)",
        increasing_line_color=BULL_COLOR,
        decreasing_line_color=BEAR_COLOR,
        increasing_fillcolor=BULL_COLOR,
        decreasing_fillcolor=BEAR_COLOR,
    )])

    x_end = daily_df.index[-1]

    # ── 2. FVG shaded zones ───────────────────────────────────────────────
    for fvg in fvgs[:8]:
        color  = ("rgba(30,100,255,0.15)" if fvg["direction"] == "bullish"
                  else "rgba(255,120,0,0.15)")
        border = ("rgba(30,100,255,0.5)"  if fvg["direction"] == "bullish"
                  else "rgba(255,120,0,0.5)")
        label = f"{'Bull' if fvg['direction'] == 'bullish' else 'Bear'} FVG"
        x0 = fvg["date"]
        if hasattr(daily_df.index[0], 'date') and hasattr(x0, 'date'):
            if x0 < daily_df.index[0]:
                x0 = daily_df.index[0]
        fig.add_shape(type="rect", x0=x0, x1=x_end,
                      y0=fvg["bottom"], y1=fvg["top"],
                      fillcolor=color, line=dict(color=border, width=1), layer="below")
        fig.add_annotation(x=x_end, y=fvg["midpoint"], text=label, showarrow=False,
                           xanchor="right", yanchor="middle",
                           font=dict(size=8, color=border))

    # ── 3. Order Block shaded zones ───────────────────────────────────────
    for ob in obs[:6]:
        color  = ("rgba(0,200,83,0.12)"  if ob["direction"] == "bullish"
                  else "rgba(213,0,0,0.12)")
        border = ("rgba(0,200,83,0.45)"  if ob["direction"] == "bullish"
                  else "rgba(213,0,0,0.45)")
        label = f"{'Bull' if ob['direction'] == 'bullish' else 'Bear'} OB"
        x0 = ob["date"]
        if hasattr(daily_df.index[0], 'date') and hasattr(x0, 'date'):
            if x0 < daily_df.index[0]:
                x0 = daily_df.index[0]
        fig.add_shape(type="rect", x0=x0, x1=x_end,
                      y0=ob["low"], y1=ob["high"],
                      fillcolor=color, line=dict(color=border, width=1), layer="below")
        fig.add_annotation(x=x_end, y=(ob["high"] + ob["low"]) / 2, text=label,
                           showarrow=False, xanchor="right", yanchor="middle",
                           font=dict(size=8, color=border))

    # ── 4. Fibonacci lines ────────────────────────────────────────────────
    fib_styles = {
        0.236: ("#888888", "dot"),
        0.382: ("#AAAAAA", "dot"),
        0.500: (NEUTRAL_COLOR, "dash"),
        0.618: (BULL_COLOR,    "dash"),
        0.705: ("#40C4FF",     "dash"),
        0.786: ("#CE93D8",     "dot"),
    }
    for level, (color, dash) in fib_styles.items():
        price = fib.get(level)
        if price is None:
            continue
        fig.add_hline(y=price, line=dict(color=color, dash=dash, width=1),
                      annotation_text=f"Fib {level:.3f} ${price:,.0f}",
                      annotation_position="left",
                      annotation_font=dict(size=8, color=color))

    # ── 5. Key level lines ────────────────────────────────────────────────
    kl_styles = {
        "PWH": (BTC_COLOR,   "solid", 1.5, "PWH"),
        "PWL": (BTC_COLOR,   "solid", 1.5, "PWL"),
        "PMH": ("#FF6D00",   "dash",  1.5, "PMH"),
        "PML": ("#FF6D00",   "dash",  1.5, "PML"),
        "CMH": ("#40C4FF",   "dot",   1.0, "CMH"),
        "CML": ("#40C4FF",   "dot",   1.0, "CML"),
        "CWH": ("#88CCFF",   "dot",   1.0, "CWH"),
        "CWL": ("#88CCFF",   "dot",   1.0, "CWL"),
    }
    for kl_key, (color, dash, width, label) in kl_styles.items():
        price = key_levels.get(kl_key)
        if price is None:
            continue
        fig.add_hline(y=price, line=dict(color=color, dash=dash, width=width),
                      annotation_text=f"{label} ${price:,.0f}",
                      annotation_position="right",
                      annotation_font=dict(size=8, color=color))

    # ── 6. Trade entry / stop / target lines ─────────────────────────────
    trade_colors = ["#FFFFFF", BTC_COLOR, "#CE93D8"]
    for trade in trades:
        if trade["direction"] == "WAIT":
            continue
        tid   = trade["id"] - 1
        color = trade_colors[tid] if tid < len(trade_colors) else "#AAAAAA"
        prefix = f"T{trade['id']}"

        for price, suffix, dash in [
            (trade.get("entry"),   "Entry", "solid"),
            (trade.get("stop"),    "Stop",  "dash"),
            (trade.get("target1"), "TP1",   "dot"),
            (trade.get("target2"), "TP2",   "dot"),
        ]:
            if price is None:
                continue
            fig.add_hline(y=price, line=dict(color=color, dash=dash, width=1),
                          annotation_text=f"{prefix} {suffix} ${price:,.0f}",
                          annotation_position="left",
                          annotation_font=dict(size=8, color=color))

    _apply_layout(
        fig,
        title="ICT Levels — Daily Bitcoin (BTC-USD)",
        height=560,
        xaxis=dict(rangeslider=dict(visible=False), type="date", gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$", zeroline=False),
    )
    return fig
