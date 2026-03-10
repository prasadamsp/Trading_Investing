# =============================================================================
# Oil Weekly Bias Dashboard — Chart Builders (Plotly)
# =============================================================================
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config

# Theme colours
BULL_COLOR    = "#00C853"
BEAR_COLOR    = "#D50000"
NEUTRAL_COLOR = "#FFD740"
OIL_COLOR     = "#FF6D00"    # WTI orange
BRENT_COLOR   = "#CE93D8"    # Brent purple
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
# WTI Price + Moving Averages
# ---------------------------------------------------------------------------

def chart_oil_price_ma(prices: dict, ma_data: dict) -> go.Figure:
    """WTI and Brent weekly price with MAs overlay."""
    wti   = prices.get("wti",   pd.DataFrame()).get("Close", pd.Series())
    brent = prices.get("brent", pd.DataFrame()).get("Close", pd.Series())

    if wti.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=wti.index, y=wti.values,
        name="WTI (CL=F)", line=dict(color=OIL_COLOR, width=2),
    ))
    if not brent.empty:
        fig.add_trace(go.Scatter(
            x=brent.index, y=brent.values,
            name="Brent (BZ=F)", line=dict(color=BRENT_COLOR, width=1.5, dash="dot"),
        ))

    colors = {20: "#40C4FF", 50: "#FFD740", 200: "#69F0AE"}
    for p, data in ma_data.items():
        ma_series = wti.rolling(p).mean()
        fig.add_trace(go.Scatter(
            x=ma_series.index, y=ma_series.values,
            name=f"{p}W MA", line=dict(color=colors.get(p, "#888"), width=1.2, dash="dot"),
        ))

    _apply_layout(fig, title="WTI & Brent Crude — Weekly + MAs", height=350,
                  yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$"))
    return fig


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def chart_rsi(prices: dict) -> go.Figure:
    """RSI (14W) for WTI."""
    import numpy as np
    wti = prices.get("wti", pd.DataFrame()).get("Close", pd.Series())
    if wti.empty:
        return go.Figure()

    delta    = wti.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi_s    = 100 - (100 / (1 + rs))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rsi_s.index, y=rsi_s.values,
        name="RSI (14)", line=dict(color="#40C4FF", width=1.8),
        fill="tozeroy", fillcolor="rgba(64,196,255,0.08)",
    ))
    for level, color, label in [(70, BEAR_COLOR, "OB 70"), (50, NEUTRAL_COLOR, "50"), (30, BULL_COLOR, "OS 30")]:
        fig.add_hline(y=level, line=dict(color=color, dash="dot", width=1),
                      annotation_text=label, annotation_position="right")

    _apply_layout(fig, title="RSI (14) — WTI Weekly", height=200,
                  yaxis=dict(range=[0, 100], gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def chart_macd(prices: dict) -> go.Figure:
    """MACD histogram + lines for WTI."""
    wti = prices.get("wti", pd.DataFrame()).get("Close", pd.Series())
    if wti.empty:
        return go.Figure()

    ema_fast    = wti.ewm(span=config.MACD_FAST,   adjust=False).mean()
    ema_slow    = wti.ewm(span=config.MACD_SLOW,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=config.MACD_SIGNAL, adjust=False).mean()
    histogram   = macd_line - signal_line

    bar_colors = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in histogram.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=histogram.index, y=histogram.values,
                         name="Histogram", marker_color=bar_colors, opacity=0.7))
    fig.add_trace(go.Scatter(x=macd_line.index, y=macd_line.values,
                             name="MACD", line=dict(color="#40C4FF", width=1.5)))
    fig.add_trace(go.Scatter(x=signal_line.index, y=signal_line.values,
                             name="Signal", line=dict(color=NEUTRAL_COLOR, width=1.2, dash="dot")))
    fig.add_hline(y=0, line=dict(color="#555", width=1))

    _apply_layout(fig, title="MACD — WTI Weekly", height=220)
    return fig


# ---------------------------------------------------------------------------
# COT Chart
# ---------------------------------------------------------------------------

def chart_cot(cot_df: pd.DataFrame) -> go.Figure:
    """COT managed money net positions for WTI."""
    if cot_df.empty or "noncomm_net" not in cot_df.columns:
        fig = go.Figure()
        fig.add_annotation(text="COT data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="COT — Non-Commercial Net Positions (WTI)", height=250)
        return fig

    net = cot_df["noncomm_net"].dropna()
    bar_colors = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in net.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=net.index, y=net.values,
                         name="Net Spec Long", marker_color=bar_colors, opacity=0.8))
    fig.add_hline(y=0, line=dict(color="#555", width=1))

    _apply_layout(fig, title="COT — Managed Money Net Positions (WTI Futures)", height=250)
    return fig


# ---------------------------------------------------------------------------
# ETF Flows
# ---------------------------------------------------------------------------

def chart_etf_flows(etf_data: dict) -> go.Figure:
    """Weekly price change for XLE, XOP, USO as flow proxy."""
    etf_keys = ["xle", "xop", "uso"]
    labels   = ["XLE", "XOP", "USO"]
    values   = [etf_data.get(k, {}).get("weekly_chg_pct", 0) or 0 for k in etf_keys]
    colors   = [BULL_COLOR if v >= 0 else BEAR_COLOR for v in values]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors, opacity=0.85,
        text=[f"{v:+.2f}%" for v in values], textposition="outside",
    ))
    fig.add_hline(y=0, line=dict(color="#555", width=1))
    _apply_layout(fig, title="Energy ETFs — Weekly Price Change %", height=280,
                  yaxis=dict(gridcolor=GRID_COLOR, zeroline=False, ticksuffix="%"))
    return fig


# ---------------------------------------------------------------------------
# EIA Inventory Chart
# ---------------------------------------------------------------------------

def chart_eia_inventory(eia: dict) -> go.Figure:
    """Weekly EIA crude, gasoline, and distillate inventory levels and draws."""
    crude      = eia.get("crude",      pd.Series())
    gasoline   = eia.get("gasoline",   pd.Series())
    distillate = eia.get("distillate", pd.Series())

    if crude.empty and gasoline.empty:
        fig = go.Figure()
        fig.add_annotation(text="EIA inventory data unavailable\nSet EIA_API_KEY in .env",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color="#888", size=13))
        _apply_layout(fig, title="EIA Weekly Petroleum Inventory (Mbbl)", height=300)
        return fig

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Crude Oil Stocks (Mbbl)", "Gasoline Stocks (Mbbl)"],
                        horizontal_spacing=0.08)

    if not crude.empty:
        fig.add_trace(go.Scatter(x=crude.index, y=crude.values,
                                 name="Crude", line=dict(color=OIL_COLOR, width=2)),
                      row=1, col=1)
    if not gasoline.empty:
        fig.add_trace(go.Scatter(x=gasoline.index, y=gasoline.values,
                                 name="Gasoline", line=dict(color="#40C4FF", width=2)),
                      row=1, col=2)

    _apply_layout(fig, title="EIA Weekly Petroleum Inventory", height=280)
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)
    return fig


def chart_eia_draws(eia: dict) -> go.Figure:
    """Weekly inventory draw/build as bar chart (negative = draw = bullish)."""
    labels = []
    values = []
    colors = []

    for key, label in [("crude", "Crude"), ("gasoline", "Gasoline"), ("distillate", "Distillate")]:
        s = eia.get(key, pd.Series())
        if s.empty or len(s) < 2:
            continue
        draw = float(s.iloc[-1] - s.iloc[-2])
        labels.append(label)
        values.append(round(draw, 1))
        colors.append(BULL_COLOR if draw < 0 else BEAR_COLOR)

    if not labels:
        fig = go.Figure()
        fig.add_annotation(text="EIA draw data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color="#888", size=13))
        _apply_layout(fig, title="EIA Weekly Inventory Change (Mbbl)", height=220)
        return fig

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors, opacity=0.85,
        text=[f"{v:+,.0f} Mbbl" for v in values], textposition="outside",
    ))
    fig.add_hline(y=0, line=dict(color="#555", width=1.5))
    fig.add_annotation(x=0.5, y=1.08, xref="paper", yref="paper",
                       text="Draw (negative) = Bullish | Build (positive) = Bearish",
                       showarrow=False, font=dict(size=10, color="#888"))
    _apply_layout(fig, title="EIA Weekly Inventory Change (Thousand Barrels)", height=260,
                  yaxis=dict(gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# Brent-WTI Spread
# ---------------------------------------------------------------------------

def chart_brent_wti_spread(prices: dict) -> go.Figure:
    """Brent minus WTI spread over time — geopolitical risk indicator."""
    brent = prices.get("brent", pd.DataFrame()).get("Close", pd.Series())
    wti   = prices.get("wti",   pd.DataFrame()).get("Close", pd.Series())

    if brent.empty or wti.empty:
        return go.Figure()

    spread = (brent - wti).dropna()
    bar_colors = [BULL_COLOR if v >= config.BRENT_WTI_GEOPOLITICAL_PREMIUM
                  else (BEAR_COLOR if v <= config.BRENT_WTI_CONTANGO_SIGNAL else NEUTRAL_COLOR)
                  for v in spread.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=spread.index, y=spread.values,
                         name="Brent - WTI", marker_color=bar_colors, opacity=0.8))
    fig.add_hline(y=config.BRENT_WTI_GEOPOLITICAL_PREMIUM,
                  line=dict(color=BULL_COLOR, dash="dot", width=1),
                  annotation_text=f"+${config.BRENT_WTI_GEOPOLITICAL_PREMIUM:.0f} Geopolitical Premium",
                  annotation_position="right", annotation_font=dict(size=9, color=BULL_COLOR))
    fig.add_hline(y=0, line=dict(color="#555", width=1))

    _apply_layout(fig, title="Brent-WTI Spread ($/bbl) — Geopolitical Risk Indicator", height=240,
                  yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$"))
    return fig


# ---------------------------------------------------------------------------
# OVX Chart (Oil Volatility)
# ---------------------------------------------------------------------------

def chart_ovx(prices: dict) -> go.Figure:
    """CBOE Crude Oil Volatility Index (OVX)."""
    ovx = prices.get("ovx", pd.DataFrame()).get("Close", pd.Series())
    if ovx.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ovx.index, y=ovx.values,
                             name="OVX", line=dict(color="#CE93D8", width=1.8),
                             fill="tozeroy", fillcolor="rgba(206,147,216,0.08)"))
    for level, color, label in [
        (config.OVX_VERY_HIGH,       BEAR_COLOR,    f"Very High ({config.OVX_VERY_HIGH})"),
        (config.OVX_HIGH_VOLATILITY, NEUTRAL_COLOR, f"Elevated ({config.OVX_HIGH_VOLATILITY})"),
    ]:
        fig.add_hline(y=level, line=dict(color=color, dash="dot", width=1),
                      annotation_text=label, annotation_position="right",
                      annotation_font=dict(size=9))

    _apply_layout(fig, title="OVX — CBOE Crude Oil Volatility Index", height=220,
                  yaxis=dict(gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# Rig Count Chart
# ---------------------------------------------------------------------------

def chart_rig_count(fred: dict) -> go.Figure:
    """Baker Hughes US Oil Rig Count (via FRED OILRUSA)."""
    rigs = fred.get("rig_count", pd.Series())
    if rigs.empty:
        fig = go.Figure()
        fig.add_annotation(text="Rig count unavailable (FRED_API_KEY required)",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color="#888", size=13))
        _apply_layout(fig, title="Baker Hughes US Oil Rig Count", height=220)
        return fig

    # Colour: rising rigs = bearish supply (red), falling = bullish (green)
    values = rigs.values
    colors = []
    for i, v in enumerate(values):
        if i == 0:
            colors.append(NEUTRAL_COLOR)
        else:
            colors.append(BULL_COLOR if v < values[i-1] else BEAR_COLOR)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rigs.index, y=rigs.values,
                             name="Oil Rig Count", line=dict(color="#40C4FF", width=2),
                             fill="tozeroy", fillcolor="rgba(64,196,255,0.08)"))

    _apply_layout(fig, title="Baker Hughes US Oil Rig Count (Rising = Bearish Supply Signal)", height=240,
                  yaxis=dict(gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# DXY
# ---------------------------------------------------------------------------

def chart_dxy(prices: dict) -> go.Figure:
    """US Dollar Index (inverse relationship with oil prices)."""
    dxy = prices.get("dxy", pd.DataFrame()).get("Close", pd.Series())
    if dxy.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dxy.index, y=dxy.values, name="DXY",
                             line=dict(color=NEUTRAL_COLOR, width=2),
                             fill="tozeroy", fillcolor="rgba(255,215,0,0.07)"))
    _apply_layout(fig, title="US Dollar Index (DXY) — Inverse to Oil", height=240)
    return fig


# ---------------------------------------------------------------------------
# Real Yield + Breakeven
# ---------------------------------------------------------------------------

def chart_real_yield(fred: dict) -> go.Figure:
    """10Y real yield and breakeven inflation."""
    ry = fred.get("real_yield_10y", pd.Series())
    be = fred.get("breakeven_10y",  pd.Series())

    fig = go.Figure()
    if not ry.empty:
        fig.add_trace(go.Scatter(x=ry.index, y=ry.values, name="10Y Real Yield",
                                 line=dict(color="#CE93D8", width=2)))
    if not be.empty:
        fig.add_trace(go.Scatter(x=be.index, y=be.values, name="10Y Breakeven Inflation",
                                 line=dict(color=NEUTRAL_COLOR, width=1.5, dash="dot")))
    fig.add_hline(y=0, line=dict(color=BEAR_COLOR, dash="dot", width=1),
                  annotation_text="0%", annotation_position="right")

    _apply_layout(fig, title="10Y Real Yield & Breakeven Inflation", height=260,
                  yaxis=dict(ticksuffix="%", gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# Cross-asset overview
# ---------------------------------------------------------------------------

def chart_cross_asset(prices: dict) -> go.Figure:
    """Multi-panel cross-asset chart relevant to oil."""
    assets = {
        "SPX":       prices.get("spx",     pd.DataFrame()).get("Close", pd.Series()),
        "VIX":       prices.get("vix",     pd.DataFrame()).get("Close", pd.Series()),
        "Nat Gas":   prices.get("natgas",  pd.DataFrame()).get("Close", pd.Series()),
        "Heating":   prices.get("heating", pd.DataFrame()).get("Close", pd.Series()),
        "EUR/USD":   prices.get("eurusd",  pd.DataFrame()).get("Close", pd.Series()),
        "Gold":      prices.get("gold",    pd.DataFrame()).get("Close", pd.Series()),
    }

    fig = make_subplots(rows=3, cols=2,
                        subplot_titles=list(assets.keys()),
                        vertical_spacing=0.10, horizontal_spacing=0.06)
    colors    = ["#40C4FF", "#D50000", OIL_COLOR, "#69F0AE", "#00C853", NEUTRAL_COLOR]
    positions = [(1,1), (1,2), (2,1), (2,2), (3,1), (3,2)]

    for (name, series), color, (row, col) in zip(assets.items(), colors, positions):
        if series.empty:
            continue
        fig.add_trace(go.Scatter(x=series.index, y=series.values, name=name,
                                 line=dict(color=color, width=1.5)),
                      row=row, col=col)

    _apply_layout(fig, title="Cross-Asset — Weekly", height=580)
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)
    return fig


# ---------------------------------------------------------------------------
# Bias Gauge
# ---------------------------------------------------------------------------

def chart_bias_gauge(score: float, label: str, color: str) -> go.Figure:
    """Speedometer gauge for the overall bias score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score * 100,
        number={"suffix": "", "font": {"size": 28, "color": color}},
        gauge={
            "axis": {"range": [-100, 100], "tickwidth": 1, "tickcolor": TEXT_COLOR},
            "bar": {"color": color, "thickness": 0.3},
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
    """Horizontal bar chart of bias score by group."""
    groups = list(group_scores.keys())
    scores = [group_scores[g] for g in groups]
    colors = [BULL_COLOR if s > 0 else (BEAR_COLOR if s < 0 else NEUTRAL_COLOR) for s in scores]

    fig = go.Figure(go.Bar(
        y=[g.replace("_", " ").title() for g in groups],
        x=scores,
        orientation="h",
        marker_color=colors, opacity=0.85,
        text=[f"{s:+.2f}" for s in scores], textposition="outside",
    ))
    fig.add_vline(x=0, line=dict(color="#555", width=1.5))
    _apply_layout(fig, title="Bias Score by Group", height=220,
                  xaxis=dict(range=[-1, 1], gridcolor=GRID_COLOR),
                  yaxis=dict(gridcolor=GRID_COLOR))
    return fig


# ---------------------------------------------------------------------------
# ICT Levels Chart — Daily candlestick with overlays
# ---------------------------------------------------------------------------

def chart_ict_levels(daily_df, weekly_df, trades: list, key_levels: dict,
                     fvgs: list, obs: list, fib: dict) -> go.Figure:
    """Daily candlestick with ICT overlays (FVG, OB, Fibonacci, key levels, trades)."""
    if daily_df is None or daily_df.empty or "High" not in daily_df.columns:
        fig = go.Figure()
        fig.add_annotation(text="ICT chart data unavailable", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=14))
        _apply_layout(fig, title="ICT Levels — Daily WTI (CL=F)", height=550)
        return fig

    fig = go.Figure(data=[go.Candlestick(
        x=daily_df.index,
        open=daily_df["Open"], high=daily_df["High"],
        low=daily_df["Low"],   close=daily_df["Close"],
        name="WTI (Daily)",
        increasing_line_color=BULL_COLOR, decreasing_line_color=BEAR_COLOR,
        increasing_fillcolor=BULL_COLOR,  decreasing_fillcolor=BEAR_COLOR,
    )])

    x_end = daily_df.index[-1]

    for fvg in fvgs[:8]:
        color  = "rgba(30,100,255,0.15)" if fvg["direction"] == "bullish" else "rgba(255,120,0,0.15)"
        border = "rgba(30,100,255,0.5)"  if fvg["direction"] == "bullish" else "rgba(255,120,0,0.5)"
        x0 = fvg["date"]
        if hasattr(daily_df.index[0], 'date') and hasattr(x0, 'date'):
            if x0 < daily_df.index[0]:
                x0 = daily_df.index[0]
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=fvg["bottom"], y1=fvg["top"],
                      fillcolor=color, line=dict(color=border, width=1), layer="below")
        fig.add_annotation(x=x_end, y=fvg["midpoint"],
                           text=f"{'Bull' if fvg['direction'] == 'bullish' else 'Bear'} FVG",
                           showarrow=False, xanchor="right", font=dict(size=8, color=border))

    for ob in obs[:6]:
        color  = "rgba(0,200,83,0.12)" if ob["direction"] == "bullish" else "rgba(213,0,0,0.12)"
        border = "rgba(0,200,83,0.45)" if ob["direction"] == "bullish" else "rgba(213,0,0,0.45)"
        x0 = ob["date"]
        if hasattr(daily_df.index[0], 'date') and hasattr(x0, 'date'):
            if x0 < daily_df.index[0]:
                x0 = daily_df.index[0]
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=ob["low"], y1=ob["high"],
                      fillcolor=color, line=dict(color=border, width=1), layer="below")
        fig.add_annotation(x=x_end, y=(ob["high"] + ob["low"]) / 2,
                           text=f"{'Bull' if ob['direction'] == 'bullish' else 'Bear'} OB",
                           showarrow=False, xanchor="right", font=dict(size=8, color=border))

    fib_styles = {
        0.236: ("#888888", "dot"), 0.382: ("#AAAAAA", "dot"),
        0.500: (NEUTRAL_COLOR, "dash"), 0.618: (BULL_COLOR, "dash"),
        0.705: ("#40C4FF", "dash"),     0.786: ("#CE93D8", "dot"),
    }
    for level, (color, dash) in fib_styles.items():
        price = fib.get(level)
        if price is None:
            continue
        fig.add_hline(y=price, line=dict(color=color, dash=dash, width=1),
                      annotation_text=f"Fib {level:.3f} ${price:,.2f}",
                      annotation_position="left", annotation_font=dict(size=8, color=color))

    kl_styles = {
        "PWH": (OIL_COLOR,   "solid", 1.5, "PWH"),
        "PWL": (OIL_COLOR,   "solid", 1.5, "PWL"),
        "PMH": ("#FF9800",   "dash",  1.5, "PMH"),
        "PML": ("#FF9800",   "dash",  1.5, "PML"),
        "CMH": ("#40C4FF",   "dot",   1.0, "CMH"),
        "CML": ("#40C4FF",   "dot",   1.0, "CML"),
    }
    for kl_key, (color, dash, width, label) in kl_styles.items():
        price = key_levels.get(kl_key)
        if price is None:
            continue
        fig.add_hline(y=price, line=dict(color=color, dash=dash, width=width),
                      annotation_text=f"{label} ${price:,.2f}", annotation_position="right",
                      annotation_font=dict(size=8, color=color))

    trade_colors = ["#FFFFFF", OIL_COLOR, "#CE93D8"]
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
                          annotation_text=f"{prefix} {suffix} ${price:,.2f}",
                          annotation_position="left", annotation_font=dict(size=8, color=color))

    _apply_layout(fig, title="ICT Levels — Daily WTI (CL=F)", height=560,
                  xaxis=dict(rangeslider=dict(visible=False), type="date", gridcolor=GRID_COLOR),
                  yaxis=dict(gridcolor=GRID_COLOR, tickprefix="$", zeroline=False))
    return fig
