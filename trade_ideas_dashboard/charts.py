# =============================================================================
# Trade Ideas Dashboard — Plotly Charts
# =============================================================================
"""
All chart builders return Plotly Figure objects with a consistent dark theme.

chart_trade_card()      — 4H mini-chart with entry/stop/target + OB/FVG zones
chart_weinstein_stage() — Weekly price + 30W MA stage chart (52 weeks)
chart_cot_commercial()  — Commercial hedger net position history
chart_cot_table()       — Returns a styled DataFrame for Streamlit st.dataframe
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config

# ---------------------------------------------------------------------------
# Dark theme defaults
# ---------------------------------------------------------------------------

_DARK_BG     = "#0E1117"
_PANEL_BG    = "#161B22"
_GRID_COLOR  = "#21262D"
_TEXT_COLOR  = "#C9D1D9"
_ACCENT_BULL = "#00C853"
_ACCENT_BEAR = "#D50000"
_ACCENT_NEU  = "#FFD740"
_LINE_COLOR  = "#58A6FF"

_LAYOUT_BASE = dict(
    paper_bgcolor = _DARK_BG,
    plot_bgcolor  = _PANEL_BG,
    font          = dict(color=_TEXT_COLOR, family="monospace", size=11),
    xaxis         = dict(gridcolor=_GRID_COLOR, showgrid=True, zeroline=False),
    yaxis         = dict(gridcolor=_GRID_COLOR, showgrid=True, zeroline=False),
    margin        = dict(l=40, r=20, t=30, b=30),
    showlegend    = True,
    legend        = dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
)


def _base_layout(**kwargs) -> dict:
    layout = dict(_LAYOUT_BASE)
    layout.update(kwargs)
    return layout


# ---------------------------------------------------------------------------
# Trade Card Mini-Chart (4H)
# ---------------------------------------------------------------------------

def chart_trade_card(
    df_4h: pd.DataFrame,
    idea: dict,
    height: int = 380,
) -> go.Figure:
    """
    4H candlestick with entry/stop/target horizontal lines,
    Order Block rectangle, and FVG zone overlay.
    """
    if df_4h.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout(title="No 4H data available", height=height))
        return fig

    # Show last 60 bars
    df = df_4h.tail(60).copy()

    direction = idea.get("direction", "LONG")
    is_long   = direction == "LONG"
    clr       = _ACCENT_BULL if is_long else _ACCENT_BEAR

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x     = df.index,
        open  = df["Open"],
        high  = df["High"],
        low   = df["Low"],
        close = df["Close"],
        name  = "Price",
        increasing_line_color  = _ACCENT_BULL,
        decreasing_line_color  = _ACCENT_BEAR,
        increasing_fillcolor   = "rgba(0,200,83,0.3)",
        decreasing_fillcolor   = "rgba(213,0,0,0.3)",
        showlegend = False,
    ))

    x_end = df.index[-1]
    x_start = df.index[max(0, len(df) - 20)]

    def _hline(price: float, label: str, color: str, dash: str = "dash"):
        fig.add_shape(
            type="line",
            x0=x_start, x1=x_end,
            y0=price, y1=price,
            line=dict(color=color, width=1.5, dash=dash),
        )
        fig.add_annotation(
            x=x_end, y=price,
            text=f"  {label}: {price:.4f}",
            showarrow=False,
            font=dict(color=color, size=9),
            xanchor="left",
        )

    # Entry / Stop / Targets
    _hline(idea["entry"],  "Entry",   clr,         "solid")
    _hline(idea["stop"],   "Stop",    _ACCENT_BEAR, "dot")
    _hline(idea["target1"],"T1",      _ACCENT_BULL, "dash")
    _hline(idea["target2"],"T2",      "#69F0AE",    "dash")

    # Order Block rectangle
    ict_data = idea.get("ict", {})
    ob_key   = "nearest_ob_long" if is_long else "nearest_ob_short"
    ob       = ict_data.get(ob_key)
    if ob:
        fig.add_shape(
            type      = "rect",
            x0        = ob["bar_date"],
            x1        = x_end,
            y0        = ob["ob_low"],
            y1        = ob["ob_high"],
            fillcolor = "rgba(0,200,83,0.1)" if is_long else "rgba(213,0,0,0.1)",
            line      = dict(color=clr, width=1, dash="dot"),
        )
        fig.add_annotation(
            x=ob["bar_date"], y=ob["ob_high"],
            text="OB",
            showarrow=False,
            font=dict(color=clr, size=9),
            yshift=6,
        )

    # FVG zone
    fvg_key = "nearest_fvg_long" if is_long else "nearest_fvg_short"
    fvg     = ict_data.get(fvg_key)
    if fvg:
        fig.add_shape(
            type      = "rect",
            x0        = fvg["bar_date"],
            x1        = x_end,
            y0        = fvg["fvg_low"],
            y1        = fvg["fvg_high"],
            fillcolor = "rgba(88,166,255,0.12)",
            line      = dict(color="#58A6FF", width=1, dash="dot"),
        )
        fig.add_annotation(
            x=fvg["bar_date"], y=fvg["fvg_high"],
            text="FVG",
            showarrow=False,
            font=dict(color="#58A6FF", size=9),
            yshift=6,
        )

    title = (f"{idea['asset_name']}  [{idea['grade']}]  {direction}  "
             f"Entry {idea['entry']:.4f}  |  RR1 1:{idea['rr1']:.1f}")
    fig.update_layout(
        **_base_layout(title=title, height=height),
        xaxis_rangeslider_visible=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Weinstein Stage Chart (Weekly)
# ---------------------------------------------------------------------------

def chart_weinstein_stage(
    weekly_df: pd.DataFrame,
    asset_name: str,
    weinstein: dict,
    weeks: int = 52,
    height: int = 320,
) -> go.Figure:
    """
    Weekly close + 30W MA + 10W MA with stage colour annotation.
    """
    if weekly_df.empty or "Close" not in weekly_df.columns:
        fig = go.Figure()
        fig.update_layout(**_base_layout(title=f"{asset_name} — no weekly data", height=height))
        return fig

    df = weekly_df.tail(weeks).copy()
    close    = df["Close"]
    ma_long  = close.rolling(config.WEINSTEIN_MA_LONG).mean()
    ma_short = close.rolling(config.WEINSTEIN_MA_SHORT).mean()

    stage = weinstein.get("stage")
    stage_label = config.STAGE_LABELS.get(stage, "Unknown")
    stage_color = config.STAGE_COLORS.get(stage, _ACCENT_NEU)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df.index, y=close,
        mode="lines",
        name="Price",
        line=dict(color=_LINE_COLOR, width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=ma_long,
        mode="lines",
        name="30W MA",
        line=dict(color=stage_color, width=2, dash="solid"),
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=ma_short,
        mode="lines",
        name="10W MA",
        line=dict(color="#FFD740", width=1, dash="dot"),
    ))

    # Volume bars (secondary y-axis if available)
    if "Volume" in df.columns and df["Volume"].sum() > 0:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.75, 0.25],
            vertical_spacing=0.04,
        )
        fig.add_trace(go.Scatter(
            x=df.index, y=close, mode="lines",
            name="Price", line=dict(color=_LINE_COLOR, width=1.5),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=ma_long, mode="lines",
            name="30W MA", line=dict(color=stage_color, width=2),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=ma_short, mode="lines",
            name="10W MA", line=dict(color="#FFD740", width=1, dash="dot"),
        ), row=1, col=1)
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            name="Volume",
            marker_color="rgba(88,166,255,0.3)",
            showlegend=False,
        ), row=2, col=1)

    title = f"{asset_name} — {stage_label}"
    fig.update_layout(
        **_base_layout(title=title, height=height),
        xaxis_rangeslider_visible=False,
    )
    return fig


# ---------------------------------------------------------------------------
# COT Commercial Hedger Chart
# ---------------------------------------------------------------------------

def chart_cot_commercial(
    cot_df: pd.DataFrame,
    asset_name: str,
    cot_result: dict,
    weeks: int = 52,
    height: int = 300,
) -> go.Figure:
    """
    Commercial hedger net position over trailing `weeks` weeks,
    with extreme level bands.
    """
    empty_fig = go.Figure()
    empty_fig.update_layout(**_base_layout(title=f"{asset_name} — COT data unavailable", height=height))

    if cot_df.empty or "comm_net" not in cot_df.columns:
        return empty_fig

    comm_net = cot_df["comm_net"].dropna().tail(weeks)
    if comm_net.empty:
        return empty_fig

    ci = cot_result.get("commercial_index")
    signal = cot_result.get("signal", "NEUTRAL")
    color  = _ACCENT_BULL if signal == "BULLISH" else (_ACCENT_BEAR if signal == "BEARISH" else _LINE_COLOR)

    mn, mx = float(comm_net.min()), float(comm_net.max())

    # Thresholds
    bull_threshold = mn + config.COT_COMMERCIAL_BULLISH / 100 * (mx - mn)
    bear_threshold = mn + config.COT_COMMERCIAL_BEARISH / 100 * (mx - mn)

    fig = go.Figure()

    # Band: bullish extreme
    fig.add_hrect(
        y0=bull_threshold, y1=mx,
        fillcolor="rgba(0,200,83,0.08)",
        line_width=0,
        annotation_text="Smart money long extreme",
        annotation_font=dict(color=_ACCENT_BULL, size=9),
        annotation_position="top left",
    )
    # Band: bearish extreme
    fig.add_hrect(
        y0=mn, y1=bear_threshold,
        fillcolor="rgba(213,0,0,0.08)",
        line_width=0,
        annotation_text="Smart money short extreme",
        annotation_font=dict(color=_ACCENT_BEAR, size=9),
        annotation_position="bottom left",
    )

    fig.add_trace(go.Scatter(
        x=comm_net.index,
        y=comm_net.values,
        mode="lines+markers",
        name="Comm Net",
        line=dict(color=color, width=1.5),
        marker=dict(size=3),
    ))

    fig.add_hline(y=0, line=dict(color=_GRID_COLOR, dash="dot", width=1))

    ci_text = f" | Index: {ci:.0f}%" if ci is not None else ""
    title   = f"{asset_name} COT — Commercial Net Positions{ci_text}"
    fig.update_layout(**_base_layout(title=title, height=height))
    return fig


# ---------------------------------------------------------------------------
# COT Summary Table (returns styled DataFrame)
# ---------------------------------------------------------------------------

def build_cot_table(all_indicators: dict) -> pd.DataFrame:
    """
    Build a summary table of commercial index values across all assets.
    Columns: Asset, Commercial Index, Net Position, Signal, W%R
    """
    rows = []
    for asset_key, ind_data in all_indicators.items():
        name = config.ASSETS[asset_key]["name"]
        cot  = ind_data.get("cot", {})
        wr   = ind_data.get("williams_r", {})

        ci    = cot.get("commercial_index")
        net   = cot.get("comm_net")
        sig   = cot.get("signal", "N/A")
        wr_v  = wr.get("value")

        rows.append({
            "Asset":             name,
            "Comm Index %":      f"{ci:.0f}" if ci is not None else "—",
            "Net Position":      f"{net:,}" if net is not None else "—",
            "COT Signal":        sig,
            "Williams %R":       f"{wr_v:.1f}" if wr_v is not None else "—",
        })

    return pd.DataFrame(rows)
