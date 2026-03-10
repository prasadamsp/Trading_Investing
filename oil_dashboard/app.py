# =============================================================================
# Oil Weekly Bias Dashboard — Streamlit App
# =============================================================================
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _get_fred_key() -> str:
    key = os.getenv("FRED_API_KEY", "")
    if not key:
        try:
            key = str(st.secrets["FRED_API_KEY"])
        except Exception:
            key = ""
    return key


def _get_eia_key() -> str:
    key = os.getenv("EIA_API_KEY", "")
    if not key:
        try:
            key = str(st.secrets["EIA_API_KEY"])
        except Exception:
            key = ""
    return key


st.set_page_config(
    page_title="Oil Weekly Bias Dashboard",
    page_icon="🛢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #0E1117; }
    .block-container { padding: 1rem 2rem; }
    .metric-card {
        background: #1E2129; border-radius: 10px;
        padding: 14px 18px; margin-bottom: 8px;
    }
    .metric-label  { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value  { font-size: 22px; font-weight: 700; color: #FAFAFA; }
    .metric-change { font-size: 13px; margin-top: 2px; }
    .bull-text  { color: #00C853; }
    .bear-text  { color: #D50000; }
    .neut-text  { color: #FFD740; }
    .score-pill {
        display: inline-block; padding: 6px 20px;
        border-radius: 50px; font-weight: 700;
        font-size: 18px; letter-spacing: 1px;
    }
    h2, h3 { color: #FF6D00 !important; }
    section[data-testid="stSidebar"] { background-color: #1E2129; }
    .stButton > button {
        background: #FF6D00; color: #fff; font-weight: 700;
        border: none; border-radius: 8px; padding: 10px 28px;
        font-size: 15px; cursor: pointer;
    }
    .stButton > button:hover { background: #E55A00; }
    .divider { border-top: 1px solid #2A2D35; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Imports (after page config)
# ---------------------------------------------------------------------------
import pandas as pd

import charts
import config
import data_fetcher
import ict_analysis
import indicators
import scoring


# ---------------------------------------------------------------------------
# Data fetching with caching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Fetching market data...")
def load_data(fred_key: str = "", eia_key: str = ""):
    return data_fetcher.fetch_all_data(fred_key=fred_key, eia_key=eia_key)


def get_data(force_refresh: bool = False):
    fred_key = _get_fred_key()
    eia_key  = _get_eia_key()
    if force_refresh:
        st.cache_data.clear()
    return load_data(fred_key=fred_key, eia_key=eia_key)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def metric_card(label: str, value: str, change: str = "", change_positive: bool | None = None):
    if change_positive is True:
        chg_class = "bull-text"
    elif change_positive is False:
        chg_class = "bear-text"
    else:
        chg_class = "neut-text"
    chg_html = f'<div class="metric-change {chg_class}">{change}</div>' if change else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {chg_html}
    </div>
    """, unsafe_allow_html=True)


def score_badge(score: float, label: str, color: str):
    st.markdown(f"""
    <div style="text-align:center; margin: 10px 0;">
        <span class="score-pill" style="background:{color}33; color:{color}; border: 2px solid {color};">
            {label}
        </span>
        <div style="color:#888; font-size:13px; margin-top:6px;">
            Score: <strong style="color:{color};">{score:+.2f}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _fmt(val, decimals: int = 2, suffix: str = "") -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}{suffix}"


def _arrow(chg) -> tuple[str, bool | None]:
    if chg is None:
        return "", None
    arrow = "▲" if chg >= 0 else "▼"
    return f"{arrow} {abs(chg):.2f}%", chg >= 0


# ---------------------------------------------------------------------------
# ── MAIN APP ─────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def main():
    # ── Header ──────────────────────────────────────────────────────────
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown("## 🛢 Oil Weekly Bias Dashboard")
        st.markdown(
            "<div style='color:#888; font-size:13px; margin-top:-12px;'>"
            "Free sources: Yahoo Finance · FRED · CFTC · EIA — All indicators weekly</div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh = st.button("Refresh Data", key="refresh_btn", use_container_width=True)

    # ── API key warnings ─────────────────────────────────────────────────
    if not _get_fred_key():
        st.warning(
            "**FRED API key not set** — macro indicators (Real Yield, CPI, Rig Count etc.) "
            "will show N/A. Add `FRED_API_KEY=your_key` to `.env`. "
            "Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).",
            icon="⚠️",
        )
    if not _get_eia_key():
        st.info(
            "**EIA API key not set** — weekly inventory draws (crude, gasoline, distillate) "
            "will show N/A. Get a free key at [eia.gov/opendata](https://www.eia.gov/opendata/) "
            "and add `EIA_API_KEY=your_key` to `.env`.",
            icon="ℹ️",
        )

    # ── Load data ────────────────────────────────────────────────────────
    data = get_data(force_refresh=refresh)

    with st.spinner("Computing indicators..."):
        ind  = indicators.build_all_indicators(data)
        bias = scoring.score_all(ind)

    fetched_at = data.get("fetched_at")
    if fetched_at:
        st.caption(f"Last updated: {fetched_at.strftime('%Y-%m-%d %H:%M:%S')}")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 1: BIAS SCORECARD
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Bias Scorecard")

    gauge_col, breakdown_col, detail_col = st.columns([1.2, 1, 1.8])

    with gauge_col:
        fig_gauge = charts.chart_bias_gauge(bias["score"], bias["label"], bias["color"])
        st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})

    with breakdown_col:
        fig_bd = charts.chart_score_breakdown(bias["group_scores"], bias["breakdown"])
        st.plotly_chart(fig_bd, use_container_width=True, config={"displayModeBar": False})

    with detail_col:
        st.markdown("**Indicator Signals**")
        all_bd = bias["breakdown"]

        def signal_row(name: str, score: int):
            icon  = "🟢" if score > 0 else ("🔴" if score < 0 else "⚪")
            label = "Bullish" if score > 0 else ("Bearish" if score < 0 else "Neutral")
            st.markdown(f"{icon} **{name}** — {label}")

        with st.expander("Macro", expanded=True):
            for k, v in all_bd["macro"].items():
                signal_row(k.replace("_", " ").title(), v)
        with st.expander("Supply / Demand"):
            for k, v in all_bd["supply"].items():
                signal_row(k.replace("_", " ").title(), v)
        with st.expander("Sentiment"):
            for k, v in all_bd["sentiment"].items():
                signal_row(k.replace("_", " ").title(), v)
        with st.expander("Technical"):
            for k, v in all_bd["technical"].items():
                signal_row(k.replace("_", " ").title(), v)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # WTI headline
    wti_price = ind.get("wti_price")
    wti_chg   = ind.get("wti_weekly_chg")
    arrow, is_pos = _arrow(wti_chg)
    chg_class = "bull-text" if is_pos else "bear-text"
    brent_price = data["prices"].get("brent", pd.DataFrame()).get("Close", pd.Series())
    brent_val   = float(brent_price.iloc[-1]) if not brent_price.empty else None
    spread_val  = ind.get("supply", {}).get("brent_wti", {}).get("spread")

    st.markdown(
        f"<h3 style='margin:0;'>WTI Crude (CL=F) &nbsp;"
        f"<span style='color:#FF6D00;'>${_fmt(wti_price, 2)}</span> &nbsp;"
        f"<span class='{chg_class}' style='font-size:16px;'>{arrow} wk</span>"
        f"&nbsp;&nbsp;|&nbsp;&nbsp;"
        f"Brent: <span style='color:#CE93D8;'>${_fmt(brent_val, 2)}</span>"
        f"&nbsp; Spread: <span style='color:#FFD740;'>${_fmt(spread_val, 2)}</span></h3>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 2: MACRO PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Macro Indicators")

    macro = ind.get("macro", {})

    mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
    with mc1:
        dxy = macro.get("dxy", {})
        arrow, pos = _arrow(dxy.get("weekly_chg"))
        metric_card("DXY (Inverse Oil)", _fmt(dxy.get("value"), 2),
                    f"{arrow} wk", change_positive=not pos if pos is not None else None)
    with mc2:
        ry = macro.get("real_yield_10y", {})
        delta = ry.get("delta")
        metric_card("10Y Real Yield", _fmt(ry.get("value"), 3, "%"),
                    f"{'▲' if delta and delta > 0 else '▼'} {abs(delta):.3f}%" if delta else "",
                    change_positive=delta < 0 if delta else None)
    with mc3:
        be = macro.get("breakeven_10y", {})
        delta = be.get("delta")
        metric_card("10Y Breakeven", _fmt(be.get("value"), 2, "%"),
                    f"{'▲' if delta and delta > 0 else '▼'} {abs(delta):.3f}%" if delta else "",
                    change_positive=delta > 0 if delta else None)
    with mc4:
        ff = macro.get("fed_funds", {})
        metric_card("Fed Funds Rate", _fmt(ff.get("value"), 2, "%"), "")
    with mc5:
        cpi = macro.get("cpi_yoy", {}).get("value")
        metric_card("CPI YoY", _fmt(cpi, 2, "%"), "High CPI = Bullish Oil",
                    change_positive=cpi > 3.0 if cpi else None)
    with mc6:
        yc = macro.get("yield_curve", {})
        val = yc.get("value")
        steep = yc.get("steepening")
        trend = "Steepening" if steep else ("Flattening" if steep is False else "")
        metric_card("Yield Curve 10Y-2Y", _fmt(val, 3, "%"), trend,
                    change_positive=steep if val and val < 0 else None)

    ch1, ch2 = st.columns(2)
    with ch1:
        st.plotly_chart(charts.chart_real_yield(data["fred"]),
                        use_container_width=True, config={"displayModeBar": False})
    with ch2:
        st.plotly_chart(charts.chart_dxy(data["prices"]),
                        use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 3: SUPPLY & DEMAND PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Supply & Demand")

    supply = ind.get("supply", {})
    eia_data  = supply.get("eia", {})
    rig_data  = supply.get("rig_count", {})
    seasonal  = supply.get("seasonal", {})
    bw_spread = supply.get("brent_wti", {})

    # Row 1: EIA inventory draws
    sd1, sd2, sd3, sd4, sd5 = st.columns(5)
    with sd1:
        draw = eia_data.get("crude_draw_mbbl")
        level = eia_data.get("crude_level")
        direction = "DRAW (Bullish)" if (draw and draw < 0) else ("BUILD (Bearish)" if (draw and draw > 0) else "")
        metric_card("Crude Inventory Chg",
                    f"{draw:+,.0f} Mbbl" if draw is not None else "N/A (EIA key)",
                    direction,
                    change_positive=(draw < 0) if draw is not None else None)
    with sd2:
        draw = eia_data.get("gasoline_draw_mbbl")
        direction = "DRAW (Bullish)" if (draw and draw < 0) else ("BUILD (Bearish)" if (draw and draw > 0) else "")
        metric_card("Gasoline Inventory Chg",
                    f"{draw:+,.0f} Mbbl" if draw is not None else "N/A (EIA key)",
                    direction,
                    change_positive=(draw < 0) if draw is not None else None)
    with sd3:
        draw = eia_data.get("distillate_draw_mbbl")
        direction = "DRAW (Bullish)" if (draw and draw < 0) else ("BUILD (Bearish)" if (draw and draw > 0) else "")
        metric_card("Distillate Inventory Chg",
                    f"{draw:+,.0f} Mbbl" if draw is not None else "N/A (EIA key)",
                    direction,
                    change_positive=(draw < 0) if draw is not None else None)
    with sd4:
        rig_val = rig_data.get("value")
        rig_chg = rig_data.get("weekly_chg")
        rig_dir = f"{'▲' if rig_chg and rig_chg > 0 else '▼'} {abs(rig_chg):.0f} rigs wk" if rig_chg else ""
        metric_card("US Oil Rig Count",
                    f"{rig_val:.0f}" if rig_val else "N/A (FRED key)",
                    rig_dir + " (Rising = Bearish Supply)",
                    change_positive=(rig_chg < 0) if rig_chg else None)
    with sd5:
        s_score = seasonal.get("score", 0)
        s_name  = seasonal.get("season_name", "")
        metric_card("Seasonal Demand",
                    f"{s_score:+.1f}",
                    s_name,
                    change_positive=(s_score > 0.2) if s_score is not None else None)

    # Row 1b: EIA crude imports (monthly — trend only)
    imports_data = supply.get("imports", {})
    imp_mbpd = imports_data.get("latest_mbpd")
    imp_yoy  = imports_data.get("yoy_pct")
    imp_rise = imports_data.get("rising")
    imp_trend = (f"{'▲' if imp_rise else '▼'} {abs(imp_yoy):.1f}% YoY — "
                 f"{'Rising (Bearish)' if imp_rise else 'Falling (Bullish)'}")  \
                if imp_yoy is not None else ""
    imp_col, _ = st.columns([1, 4])
    with imp_col:
        metric_card(
            "Crude Imports (Monthly, Mbbl/d)",
            f"{imp_mbpd:,.0f}" if imp_mbpd is not None else "N/A (EIA key)",
            imp_trend,
            change_positive=(not imp_rise) if imp_rise is not None else None,
        )

    # Row 2: Brent-WTI spread
    bw1, bw2 = st.columns(2)
    with bw1:
        spread = bw_spread.get("spread")
        widening = bw_spread.get("widening")
        spread_trend = "Widening (Bullish)" if widening else ("Narrowing" if widening is False else "")
        metric_card("Brent-WTI Spread ($/bbl)",
                    f"${_fmt(spread, 2)}",
                    spread_trend + (f" | Geopolitical premium" if spread and spread >= config.BRENT_WTI_GEOPOLITICAL_PREMIUM else ""),
                    change_positive=(spread and spread >= config.BRENT_WTI_GEOPOLITICAL_PREMIUM))
    with bw2:
        crude_level = eia_data.get("crude_level")
        crude_avg   = eia_data.get("crude_5yr_avg")
        if crude_level and crude_avg:
            vs_avg = crude_level - crude_avg
            metric_card("Crude Stocks vs 5Y Avg",
                        f"{crude_level:,.0f} Mbbl",
                        f"{vs_avg:+,.0f} vs 5Y avg — {'Above avg (Bearish)' if vs_avg > 0 else 'Below avg (Bullish)'}",
                        change_positive=(vs_avg < 0))
        else:
            metric_card("Crude Stocks vs 5Y Avg", "N/A (EIA key)", "")

    # Charts: EIA draws, Brent-WTI spread, rig count
    eia_col, spread_col = st.columns(2)
    with eia_col:
        st.plotly_chart(charts.chart_eia_draws(data["eia"]),
                        use_container_width=True, config={"displayModeBar": False})
    with spread_col:
        st.plotly_chart(charts.chart_brent_wti_spread(data["prices"]),
                        use_container_width=True, config={"displayModeBar": False})

    st.plotly_chart(charts.chart_eia_inventory(data["eia"]),
                    use_container_width=True, config={"displayModeBar": False})
    st.plotly_chart(charts.chart_rig_count(data["fred"]),
                    use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 4: SENTIMENT — COT & ETF
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Sentiment — COT & ETF Flows")

    sent = ind.get("sentiment", {})
    cot_data = sent.get("cot", {})
    etf_data = sent.get("etf", {})

    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        net = cot_data.get("net_pos")
        metric_card("COT Net Spec Long (WTI)", f"{net:,}" if net else "N/A")
    with sc2:
        ci = cot_data.get("cot_index")
        extreme = "Extreme Long (Contrarian Bearish)" if cot_data.get("extreme_long") else \
                  ("Extreme Short (Contrarian Bullish)" if cot_data.get("extreme_short") else "")
        metric_card("COT Index (52W %ile)", _fmt(ci, 1), extreme,
                    change_positive=(ci < 20) if ci else None)
    with sc3:
        avg_flow = etf_data.get("combined_flow_avg_pct")
        metric_card("ETF Avg Flow (wk %)", _fmt(avg_flow, 2, "%"),
                    "XLE + XOP + USO combined",
                    change_positive=avg_flow >= 0 if avg_flow is not None else None)
    with sc4:
        ovx_data = ind.get("technical", {}).get("ovx", {})
        ovx_val  = ovx_data.get("value")
        ovx_chg  = ovx_data.get("weekly_chg")
        ovx_str, ovx_pos = _arrow(ovx_chg)
        metric_card("OVX (Oil Volatility)", _fmt(ovx_val, 1),
                    f"{ovx_str} wk | {'Very High' if ovx_data.get('very_high_vol') else 'Elevated' if ovx_data.get('high_vol') else 'Normal'}",
                    change_positive=not ovx_pos if ovx_pos is not None else None)

    fig_cot = charts.chart_cot(data["cot"])
    st.plotly_chart(fig_cot, use_container_width=True, config={"displayModeBar": False})

    # ETF details
    st.markdown("**Energy ETFs**")
    etf_keys   = ["xle", "xop", "uso"]
    etf_labels = ["XLE", "XOP", "USO"]
    etf_desc   = [
        "Energy Select Sector SPDR (Large-Cap)",
        "S&P Oil & Gas E&P (Small/Mid-Cap)",
        "United States Oil Fund (WTI Futures)",
    ]
    e_cols = st.columns(3)
    for i, (key, label, desc) in enumerate(zip(etf_keys, etf_labels, etf_desc)):
        d = etf_data.get(key, {})
        price = d.get("price")
        chg   = d.get("weekly_chg_pct")
        aum   = d.get("aum_m")
        arrow_str, is_pos = _arrow(chg)
        aum_str = f"AUM ~${aum:,.0f}M" if aum else ""
        with e_cols[i]:
            metric_card(f"{label} — {desc}", _fmt(price), f"{arrow_str} wk | {aum_str}",
                        change_positive=is_pos)

    fig_etf = charts.chart_etf_flows(etf_data)
    st.plotly_chart(fig_etf, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 5: TECHNICAL PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Technical — Weekly")

    tech = ind.get("technical", {})
    mas  = tech.get("moving_averages", {})
    rsi  = tech.get("rsi")
    macd = tech.get("macd", {})
    ovx  = tech.get("ovx", {})

    tc1, tc2, tc3, tc4, tc5, tc6 = st.columns(6)
    for col, period in zip([tc1, tc2, tc3], config.WEEKLY_MA_PERIODS):
        ma_d  = mas.get(period, {})
        above = ma_d.get("above")
        diff  = ma_d.get("pct_diff")
        with col:
            metric_card(f"{period}W MA", _fmt(ma_d.get("ma")),
                        f"{'Above' if above else 'Below'} ({diff:+.2f}%)" if diff is not None else "",
                        change_positive=above)
    with tc4:
        rsi_zone = ("Momentum 50-70" if (rsi and 50 <= rsi <= 70) else
                    ("Overbought >75" if (rsi and rsi > 75) else
                     ("Weak <35" if (rsi and rsi < 35) else "Neutral")))
        metric_card("RSI (14W)", _fmt(rsi, 1), rsi_zone,
                    change_positive=(rsi and 50 <= rsi <= 70))
    with tc5:
        macd_bull  = macd.get("bullish")
        macd_cross = macd.get("crossing_up")
        macd_label = "Bullish Cross!" if macd_cross else ("Above 0" if macd_bull else "Below 0")
        metric_card("MACD Weekly", _fmt(macd.get("histogram"), 4), macd_label,
                    change_positive=macd_bull)
    with tc6:
        ovx_val = ovx.get("value")
        ovx_lbl = ("Very High Volatility" if ovx.get("very_high_vol")
                   else "Elevated Volatility" if ovx.get("high_vol") else "Normal Volatility")
        metric_card("OVX", _fmt(ovx_val, 1), ovx_lbl,
                    change_positive=not ovx.get("high_vol"))

    st.plotly_chart(charts.chart_oil_price_ma(data["prices"], mas),
                    use_container_width=True, config={"displayModeBar": False})

    rsi_col, macd_col = st.columns(2)
    with rsi_col:
        st.plotly_chart(charts.chart_rsi(data["prices"]),
                        use_container_width=True, config={"displayModeBar": False})
    with macd_col:
        st.plotly_chart(charts.chart_macd(data["prices"]),
                        use_container_width=True, config={"displayModeBar": False})

    st.plotly_chart(charts.chart_ovx(data["prices"]),
                    use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 6: CROSS-ASSET PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Cross-Asset")

    cross = ind.get("cross_asset", {})

    xc1, xc2, xc3, xc4, xc5, xc6 = st.columns(6)
    cross_items = [
        (xc1, "SPX",     cross.get("spx",     {}), True),    # rising SPX = bullish oil (demand)
        (xc2, "VIX",     cross.get("vix",     {}), False),   # rising VIX = bearish oil
        (xc3, "Nat Gas", cross.get("natgas",  {}), True),    # rising NG = energy complex bullish
        (xc4, "Heating", cross.get("heating", {}), True),    # rising HO = demand
        (xc5, "EUR/USD", cross.get("eurusd",  {}), True),    # weaker USD = bullish oil
        (xc6, "Gold",    cross.get("gold",    {}), True),    # rising gold = risk-off / inflation
    ]

    for col, label, d, rising_is_bullish in cross_items:
        val = d.get("value")
        chg = d.get("weekly_chg")
        arrow_str, is_pos = _arrow(chg)
        oil_pos = is_pos if rising_is_bullish else (not is_pos if is_pos is not None else None)
        with col:
            metric_card(label, _fmt(val, 4 if label == "EUR/USD" else 2),
                        f"{arrow_str} wk", change_positive=oil_pos)

    st.plotly_chart(charts.chart_cross_asset(data["prices"]),
                    use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 7: ICT TRADE IDEAS
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### ICT Trade Ideas (Daily WTI)")
    st.caption(
        "Educational ICT analysis only — not financial advice. "
        "Concepts applied: Market Structure · Order Blocks · Fair Value Gaps · Fibonacci OTE (0.618–0.705) · Key Levels"
    )

    monthly_df = data.get("monthly_oil", pd.DataFrame())
    weekly_df  = data.get("weekly_oil",  pd.DataFrame())
    daily_df   = data.get("daily_oil",   pd.DataFrame())

    if monthly_df.empty or weekly_df.empty or daily_df.empty:
        st.warning("ICT data unavailable — price DataFrames not loaded. Click Refresh Data.")
    else:
        with st.spinner("Running ICT analysis..."):
            ict_trades     = ict_analysis.generate_ict_trades(
                monthly_df, weekly_df, daily_df, bias["score"])
            ict_key_levels = ict_analysis.get_key_levels(monthly_df, weekly_df)
            sh, sl, _      = ict_analysis._find_major_swing(daily_df, lookback_bars=30)
            if sh - sl < float(daily_df["Close"].iloc[-1]) * 0.02:
                sh, sl, _ = ict_analysis._find_major_swing(daily_df, lookback_bars=60)
            ict_fib        = ict_analysis.calc_fibonacci_levels(sh, sl)
            all_fvgs       = (
                [f for f in ict_analysis.find_fvgs(weekly_df) if not f["filled"]] +
                [f for f in ict_analysis.find_fvgs(daily_df)  if not f["filled"]]
            )
            all_obs        = (
                [o for o in ict_analysis.find_order_blocks(weekly_df) if o["valid"]] +
                [o for o in ict_analysis.find_order_blocks(daily_df)  if o["valid"]]
            )

        # Key levels
        kl = ict_key_levels
        kl1, kl2, kl3, kl4 = st.columns(4)
        with kl1:
            metric_card("Prev Month High (PMH)", _fmt(kl.get("PMH"), 2))
        with kl2:
            metric_card("Prev Month Low (PML)",  _fmt(kl.get("PML"), 2))
        with kl3:
            metric_card("Prev Week High (PWH)",  _fmt(kl.get("PWH"), 2))
        with kl4:
            metric_card("Prev Week Low (PWL)",   _fmt(kl.get("PWL"), 2))

        if ict_fib:
            fifty   = ict_fib.get(0.5)
            ote_l   = ict_fib.get(0.618)
            ote_h   = ict_fib.get(0.705)
            current = ind.get("wti_price")
            zone_label = ""
            if current and fifty:
                zone_label = "🔵 Discount Zone" if current < fifty else "🔴 Premium Zone"
            st.markdown(
                f"<div style='font-size:12px; color:#888; margin: 4px 0 12px 0;'>"
                f"Swing: ${_fmt(ict_fib.get('swing_low'), 2)} → ${_fmt(ict_fib.get('swing_high'), 2)} &nbsp;|&nbsp; "
                f"50% (mid): <strong style='color:#FFD740;'>${_fmt(fifty, 2)}</strong> &nbsp;|&nbsp; "
                f"OTE Zone: ${_fmt(ote_h, 2)} – ${_fmt(ote_l, 2)} &nbsp;|&nbsp; {zone_label}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Trade cards
        tc1, tc2, tc3 = st.columns(3)
        trade_titles = [
            "Trade 1 — Primary Trend",
            "Trade 2 — OTE Retracement",
            "Trade 3 — Liquidity Hunt",
        ]
        trade_colors = ["#FFFFFF", "#FF6D00", "#CE93D8"]

        for col, trade, title in zip([tc1, tc2, tc3], ict_trades, trade_titles):
            d    = trade["direction"]
            conf = trade["confidence"]
            is_low = (conf == "LOW")

            badge_color = "#00C853" if d == "LONG" else ("#D50000" if d == "SHORT" else "#FFD740")
            conf_color  = (
                "#00C853" if conf == "HIGH"
                else ("#FFD740" if conf == "MEDIUM" else "#888888")
            )
            card_style = f"opacity:0.55; border:1px solid #444;" if is_low else ""
            low_banner = (
                f'<div style="background:#FF6D0022; border:1px solid #FF6D00; '
                f'border-radius:4px; padding:4px 8px; margin-bottom:8px; '
                f'font-size:10px; color:#FF6D00; text-align:center;">'
                f'LOW SIGNAL — avoid or use minimal size</div>'
            ) if is_low else ""

            with col:
                st.markdown(f"""
                <div class="metric-card" style="{card_style}">
                    {low_banner}
                    <div style="font-size:11px; color:#888; margin-bottom:6px;">{title}</div>
                    <div style="text-align:center; margin-bottom:10px;">
                        <span class="score-pill"
                              style="background:{badge_color}33; color:{badge_color};
                                     border:2px solid {badge_color}; font-size:14px; padding:4px 16px;">
                            {d}
                        </span>
                    </div>
                    <div class="metric-label" style="margin-bottom:6px;">{trade['setup_name']}</div>
                    <div style="font-size:12px; color:#FAFAFA; line-height:1.8;">
                        <b>Entry:</b> &nbsp;${_fmt(trade['entry'], 2)}<br>
                        <b>Stop: </b> &nbsp;${_fmt(trade['stop'],  2)}<br>
                        <b>TP1:  </b> &nbsp;${_fmt(trade['target1'], 2)}
                            <span style="color:#888; font-size:11px;">&nbsp;(R:R {_fmt(trade['rr1'], 2)})</span><br>
                        <b>TP2:  </b> &nbsp;${_fmt(trade['target2'], 2)}
                            <span style="color:#888; font-size:11px;">&nbsp;(R:R {_fmt(trade['rr2'], 2)})</span>
                    </div>
                    <div style="margin:8px 0 4px; font-size:11px;">
                        Confidence: <span style="color:{conf_color}; font-weight:700;">{conf}</span>
                        &nbsp;|&nbsp; TF: <span style="color:#888;">{trade['timeframe']}</span>
                    </div>
                    <div style="font-size:11px; color:#aaa; line-height:1.5;
                                border-top:1px solid #2A2D35; padding-top:6px;">
                        {trade['rationale']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if trade.get("key_levels_used"):
                    st.caption("📌 " + " · ".join(trade["key_levels_used"]))

        fig_ict = charts.chart_ict_levels(
            daily_df=daily_df, weekly_df=weekly_df,
            trades=ict_trades, key_levels=ict_key_levels,
            fvgs=all_fvgs, obs=all_obs, fib=ict_fib,
        )
        st.plotly_chart(fig_ict, use_container_width=True, config={"displayModeBar": False})

    # ════════════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════════════
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.caption(
        "Data: Yahoo Finance (prices, ETFs) · FRED API (macro, rig count) · "
        "CFTC (COT — WTI #067651) · EIA Open Data API (inventory) — all free sources. "
        "This dashboard is for informational purposes only. Not financial advice."
    )


if __name__ == "__main__":
    main()
