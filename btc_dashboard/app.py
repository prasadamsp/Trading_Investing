# =============================================================================
# Bitcoin Weekly Bias Dashboard — Streamlit App
# =============================================================================
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _get_fred_key() -> str:
    """Read FRED key from .env (local) or Streamlit secrets (cloud)."""
    key = os.getenv("FRED_API_KEY", "")
    if not key:
        try:
            key = str(st.secrets["FRED_API_KEY"])
        except Exception:
            key = ""
    return key


st.set_page_config(
    page_title="Bitcoin Weekly Bias Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS — Bitcoin orange theme
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
    h2, h3 { color: #F7931A !important; }
    section[data-testid="stSidebar"] { background-color: #1E2129; }
    .stButton > button {
        background: #F7931A; color: #000; font-weight: 700;
        border: none; border-radius: 8px; padding: 10px 28px;
        font-size: 15px; cursor: pointer;
    }
    .stButton > button:hover { background: #E07B0E; }
    .divider { border-top: 1px solid #2A2D35; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Imports (after page config)
# ---------------------------------------------------------------------------
import pandas as pd

import charts
import data_fetcher
import ict_analysis
import indicators
import scoring
import config


# ---------------------------------------------------------------------------
# Data fetching with caching
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Fetching market data...")
def load_data(fred_key: str = ""):
    return data_fetcher.fetch_all_data(fred_key=fred_key)


def get_data(force_refresh: bool = False):
    fred_key = _get_fred_key()
    if force_refresh:
        st.cache_data.clear()
    return load_data(fred_key=fred_key)


# ---------------------------------------------------------------------------
# Helper: coloured metric card
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


def _fmt(val, decimals: int = 2, suffix: str = "", prefix: str = "") -> str:
    if val is None:
        return "N/A"
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def _fmt_btc(val) -> str:
    """Format BTC price with commas and no decimal places."""
    if val is None:
        return "N/A"
    return f"${val:,.0f}"


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
        st.markdown("## ₿ Bitcoin Weekly Bias Dashboard")
        st.markdown(
            "<div style='color:#888; font-size:13px; margin-top:-12px;'>"
            "Free sources: Yahoo Finance · FRED · CFTC · Alternative.me Fear & Greed · All indicators weekly"
            "</div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh = st.button("Refresh Data", key="refresh_btn", use_container_width=True)

    # ── FRED key warning ─────────────────────────────────────────────────
    if not os.getenv("FRED_API_KEY"):
        st.warning(
            "**FRED API key not set** — macro indicators (Real Yield, Breakeven, CPI, PCE, Yield Curve) "
            "will show N/A. Add `FRED_API_KEY=your_key` to the `.env` file. "
            "Get a free key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).",
            icon="⚠️",
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
        fig_breakdown = charts.chart_score_breakdown(bias["group_scores"], bias["breakdown"])
        st.plotly_chart(fig_breakdown, use_container_width=True, config={"displayModeBar": False})

    with detail_col:
        st.markdown("**Indicator Signals**")
        all_bd = bias["breakdown"]

        def signal_row(name: str, score: int):
            icon  = "🟢" if score > 0 else ("🔴" if score < 0 else "⚪")
            label = "Bullish" if score > 0 else ("Bearish" if score < 0 else "Neutral")
            st.markdown(f"{icon} **{name}** — {label}")

        with st.expander("Macro + BTC Cycle", expanded=True):
            for k, v in all_bd["macro"].items():
                signal_row(k.replace("_", " ").title(), v)

        with st.expander("Sentiment"):
            for k, v in all_bd["sentiment"].items():
                signal_row(k.replace("_", " ").title(), v if isinstance(v, int) else 0)

        with st.expander("Technical"):
            for k, v in all_bd["technical"].items():
                signal_row(k.replace("_", " ").title(), v)

        with st.expander("Cross-Asset"):
            for k, v in all_bd["cross_asset"].items():
                signal_row(k.replace("_", " ").title(), v)

    # ── Bias Narrative Summary ───────────────────────────────────────────
    def _build_narrative(bias: dict, ind: dict) -> str:
        score  = bias["score"]
        label  = bias["label"]
        grp    = bias["group_scores"]
        sent   = ind.get("sentiment", {})
        fg     = sent.get("fear_greed", {})
        fr     = sent.get("funding_rate", {})
        oi     = sent.get("open_interest", {})
        halv   = ind.get("btc_specific", {}).get("halving", {})

        bullets = []
        # Bias summary
        direction_word = "bullish" if score > 0.2 else ("bearish" if score < -0.2 else "neutral")
        bullets.append(f"**Overall bias is {label} ({score:+.2f})** — macro, sentiment, technicals, and cross-asset signals combine to a {direction_word} lean.")

        # Strongest group
        top_group  = max(grp, key=lambda k: abs(grp[k]))
        top_val    = grp[top_group]
        top_lbl    = "bullish" if top_val > 0 else "bearish"
        bullets.append(f"The **{top_group.replace('_',' ').title()}** group is the dominant driver ({top_val:+.2f}), pulling {top_lbl}.")

        # Halving context
        phase = halv.get("phase", "")
        if phase:
            bullets.append(f"BTC is in the **{phase}** halving cycle phase ({halv.get('months_since', 0):.0f} months post-April 2024 halving) → {('structural tailwind' if phase in ('Early Bull', 'Pre-Halving') else 'elevated caution zone')}.")

        # Fear & Greed
        fg_val = fg.get("value")
        if fg_val is not None:
            fg_cls = fg.get("classification", "")
            bullets.append(f"Fear & Greed Index is **{fg_val} ({fg_cls})** — {'contrarian buy signal (extreme fear)' if fg_val < 20 else ('contrarian caution (extreme greed)' if fg_val > 80 else 'neutral sentiment zone')}.")

        # Funding rate
        fr_cur = fr.get("current")
        fr_sig = fr.get("signal", "neutral")
        if fr_cur is not None:
            fr_msg = {
                "extreme_long":  f"⚠️ Perp funding at **{fr_cur:+.4f}%/8h** — extremely crowded longs; contrarian bearish risk.",
                "mild_long":     f"Perp funding at **{fr_cur:+.4f}%/8h** — mild long bias, no extreme crowding.",
                "extreme_short": f"Perp funding at **{fr_cur:+.4f}%/8h** — shorts crowded; short-squeeze potential (bullish).",
                "neutral":       f"Perp funding near neutral ({fr_cur:+.4f}%/8h) — balanced derivative positioning.",
            }.get(fr_sig, "")
            if fr_msg:
                bullets.append(fr_msg)

        # OI regime
        regime = oi.get("regime", "")
        regime_msg = {
            "confirmed_bull":      "OI rising with price — **confirmed bullish trend**; institutional money entering.",
            "bearish_distribution": "OI rising while price falls — **bearish distribution**; watch for breakdown.",
            "short_covering":       "OI falling with price rising — likely **short covering**, not fresh longs; watch breakout quality.",
            "bearish_liquidation":  "OI falling with price falling — **bearish liquidation**; trend may accelerate down.",
        }.get(regime, "")
        if regime_msg:
            bullets.append(regime_msg)

        return "\n\n".join(f"- {b}" for b in bullets)

    narrative = _build_narrative(bias, ind)
    with st.expander("Weekly Bias Summary — Key Drivers", expanded=True):
        st.markdown(narrative)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # BTC headline
    btc_price = ind.get("btc_price")
    btc_chg   = ind.get("btc_weekly_chg")
    arrow, is_pos = _arrow(btc_chg)
    chg_class = "bull-text" if is_pos else "bear-text"
    st.markdown(
        f"<h3 style='margin:0;'>Bitcoin (BTC/USD) &nbsp; "
        f"<span style='color:#F7931A;'>{_fmt_btc(btc_price)}</span> &nbsp;"
        f"<span class='{chg_class}' style='font-size:16px;'>{arrow} wk</span></h3>",
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
        metric_card("DXY", _fmt(dxy.get("value"), 2),
                    f"{arrow} wk",
                    change_positive=not pos if pos is not None else None)

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
        metric_card("CPI YoY", _fmt(macro.get("cpi_yoy", {}).get("value"), 2, "%"), "")

    with mc6:
        m2 = macro.get("m2", {})
        m2_yoy = m2.get("yoy_pct")
        metric_card("M2 Supply YoY",
                    _fmt(m2_yoy, 2, "%") if m2_yoy else "N/A",
                    "Expanding M2 = Bullish BTC" if m2_yoy and m2_yoy > 0 else "",
                    change_positive=m2_yoy > 0 if m2_yoy else None)

    # 2Y / 10Y yields + yield curve
    mc_a, mc_b, mc_c = st.columns(3)
    with mc_a:
        t2 = macro.get("treasury_2y", {})
        delta = t2.get("delta")
        metric_card("2Y Treasury Yield", _fmt(t2.get("value"), 3, "%"),
                    f"{'▲' if delta and delta > 0 else '▼'} {abs(delta):.3f}%" if delta else "",
                    change_positive=delta < 0 if delta else None)
    with mc_b:
        t10 = macro.get("treasury_10y", {})
        delta = t10.get("delta")
        metric_card("10Y Treasury Yield", _fmt(t10.get("value"), 3, "%"),
                    f"{'▲' if delta and delta > 0 else '▼'} {abs(delta):.3f}%" if delta else "",
                    change_positive=delta < 0 if delta else None)
    with mc_c:
        yc = macro.get("yield_curve", {})
        val = yc.get("value")
        steep = yc.get("steepening")
        trend = "Steepening" if steep else ("Flattening" if steep is False else "")
        metric_card("Yield Curve 10Y-2Y", _fmt(val, 3, "%"), trend, change_positive=steep)

    # Macro charts
    ch1, ch2 = st.columns(2)
    with ch1:
        fig = charts.chart_real_yield(data["fred"])
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with ch2:
        fig = charts.chart_yield_curve(data["fred"])
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    fig_dxy = charts.chart_dxy(data["prices"])
    st.plotly_chart(fig_dxy, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 3: SENTIMENT — FEAR & GREED + COT
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Sentiment — Fear & Greed · COT · ETF Flows")

    fg_data  = ind.get("sentiment", {}).get("fear_greed", {})
    cot_data = ind.get("sentiment", {}).get("cot", {})

    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        fg_val   = fg_data.get("value")
        fg_class = fg_data.get("classification", "")
        fg_chg   = fg_data.get("weekly_chg")
        extreme  = ""
        if fg_data.get("extreme_fear"):
            extreme = "Extreme Fear → Contrarian BULLISH"
        elif fg_data.get("extreme_greed"):
            extreme = "Extreme Greed → Contrarian BEARISH"
        chg_str = f"{'▲' if fg_chg and fg_chg > 0 else '▼'} {abs(fg_chg):.1f} wk" if fg_chg else ""
        metric_card(
            "Fear & Greed Index",
            f"{fg_val} — {fg_class}" if fg_val else "N/A",
            extreme or chg_str,
            change_positive=(fg_val < 40) if fg_val else None,   # fear = contrarian bullish
        )

    with sc2:
        net = cot_data.get("net_pos")
        ci  = cot_data.get("cot_index")
        extreme_cot = "Extreme Long (Contrarian Bearish)" if cot_data.get("extreme_long") else \
                      ("Extreme Short (Contrarian Bullish)" if cot_data.get("extreme_short") else "")
        metric_card("CME BTC COT %ile", _fmt(ci, 1) if ci is not None else "N/A",
                    extreme_cot, change_positive=(ci < 20) if ci is not None else None)

    with sc3:
        btc_eth = ind.get("sentiment", {}).get("btc_eth_ratio", {})
        metric_card("BTC / ETH Ratio", _fmt(btc_eth.get("value"), 2),
                    (_arrow(btc_eth.get("weekly_chg"))[0]) + " wk")

    with sc4:
        avg_flow = ind.get("sentiment", {}).get("etf", {}).get("combined_flow_avg_pct")
        metric_card("ETF Avg Flow (wk)", _fmt(avg_flow, 2, "%"),
                    change_positive=avg_flow >= 0 if avg_flow is not None else None)

    # Fear & Greed chart
    fig_fg = charts.chart_fear_greed(data.get("fear_greed", pd.DataFrame()))
    st.plotly_chart(fig_fg, use_container_width=True, config={"displayModeBar": False})

    # COT chart
    fig_cot = charts.chart_cot(data["cot"])
    st.plotly_chart(fig_cot, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 4: BITCOIN ETF PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Bitcoin Spot ETFs")

    etf_data   = ind.get("sentiment", {}).get("etf", {})
    etf_keys   = ["ibit", "fbtc", "gbtc", "arkb", "hodl", "bitb"]
    etf_labels = ["IBIT", "FBTC", "GBTC", "ARKB", "HODL", "BITB"]
    etf_desc   = [
        "BlackRock iShares BTC",
        "Fidelity Wise Origin BTC",
        "Grayscale Bitcoin Trust",
        "ARK 21Shares Bitcoin",
        "VanEck Bitcoin ETF",
        "Bitwise Bitcoin ETF",
    ]

    cols = st.columns(6)
    for i, (key, label, desc) in enumerate(zip(etf_keys, etf_labels, etf_desc)):
        d = etf_data.get(key, {})
        price = d.get("price")
        chg   = d.get("weekly_chg_pct")
        aum   = d.get("aum_m")
        arrow_str, is_pos = _arrow(chg)
        with cols[i]:
            aum_str = f"AUM ~${aum:,.0f}M" if aum else ""
            metric_card(f"{label} — {desc}", _fmt(price), f"{arrow_str} wk | {aum_str}", change_positive=is_pos)

    # BTC/ETH ratio trend
    mr1, mr2 = st.columns(2)
    with mr1:
        ratio_trend = etf_data.get("btc_eth_ratio_trend")
        icon = "▲" if ratio_trend == "rising" else ("▼" if ratio_trend == "falling" else "")
        metric_card("BTC / ETH Ratio Trend", f"{icon} {ratio_trend or 'N/A'}".strip(),
                    "Rising = BTC outperforming ETH = BTC Dominance",
                    change_positive=ratio_trend == "rising" if ratio_trend else None)
    with mr2:
        metric_card("Avg ETF Flow (wk)",
                    _fmt(etf_data.get("combined_flow_avg_pct"), 2, "%"),
                    "Positive = net inflows across BTC ETFs",
                    change_positive=(etf_data.get("combined_flow_avg_pct") or 0) >= 0)

    fig_etf = charts.chart_etf_flows(etf_data)
    st.plotly_chart(fig_etf, use_container_width=True, config={"displayModeBar": False})

    # BTC/ETH ratio chart
    fig_ratio = charts.chart_btc_eth_ratio(data["prices"])
    st.plotly_chart(fig_ratio, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 4.5: DERIVATIVES — FUNDING RATE + OPEN INTEREST
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Derivatives Market — Funding Rate & Open Interest")
    st.caption(
        "Perpetual futures data from OKX (free, no API key). "
        "Extreme positive funding = too many longs → contrarian bearish. "
        "Extreme negative = shorts crowded → squeeze potential."
    )

    fr_data  = ind.get("sentiment", {}).get("funding_rate",  {})
    oi_data  = ind.get("sentiment", {}).get("open_interest", {})

    dr1, dr2, dr3, dr4 = st.columns(4)
    with dr1:
        fr_cur = fr_data.get("current")
        fr_sig = fr_data.get("signal", "neutral")
        fr_signal_labels = {
            "extreme_long":   "⚠️ Extreme Long (Bear Risk)",
            "mild_long":      "Mild Long Bias",
            "extreme_short":  "Extreme Short (Bull Squeeze)",
            "neutral":        "Neutral",
        }
        fr_pos = {"extreme_short": True, "neutral": None, "mild_long": None, "extreme_long": False}.get(fr_sig)
        metric_card(
            "Funding Rate (/8h)",
            f"{fr_cur:+.4f}%" if fr_cur is not None else "N/A",
            fr_signal_labels.get(fr_sig, ""),
            change_positive=fr_pos,
        )
    with dr2:
        fr_avg = fr_data.get("avg_7d")
        metric_card(
            "Funding 7D Avg (/8h)",
            f"{fr_avg:+.4f}%" if fr_avg is not None else "N/A",
            "7-day average funding rate",
            change_positive=(fr_avg < 0) if fr_avg is not None else None,
        )
    with dr3:
        oi_b    = oi_data.get("current_b")
        oi_chg  = oi_data.get("oi_chg_pct")
        oi_rise = oi_data.get("oi_rising")
        metric_card(
            "Open Interest",
            f"${oi_b:.2f}B" if oi_b is not None else "N/A",
            (f"{'▲' if oi_rise else '▼'} {abs(oi_chg):.1f}% (4D)" if oi_chg is not None else ""),
            change_positive=oi_rise,
        )
    with dr4:
        regime = oi_data.get("regime", "unknown")
        regime_labels = {
            "confirmed_bull":       "Confirmed Bull",
            "bearish_distribution": "Bearish Distribution",
            "short_covering":       "Short Covering",
            "bearish_liquidation":  "Bearish Liquidation",
            "unknown":              "N/A",
        }
        regime_pos = {
            "confirmed_bull":       True,
            "short_covering":       None,
            "bearish_distribution": False,
            "bearish_liquidation":  False,
        }.get(regime)
        metric_card(
            "OI Regime",
            regime_labels.get(regime, regime),
            "OI trend vs price direction",
            change_positive=regime_pos,
        )

    dr_c1, dr_c2 = st.columns(2)
    with dr_c1:
        fig_fr = charts.chart_funding_rate(fr_data)
        st.plotly_chart(fig_fr, use_container_width=True, config={"displayModeBar": False})
    with dr_c2:
        fig_oi = charts.chart_open_interest(oi_data, data["prices"])
        st.plotly_chart(fig_oi, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 5: TECHNICAL PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Technical — Weekly")

    tech = ind.get("technical", {})
    mas  = tech.get("moving_averages", {})
    rsi  = tech.get("rsi")
    macd = tech.get("macd", {})

    tc1, tc2, tc3, tc4, tc5 = st.columns(5)
    for col, period in zip([tc1, tc2, tc3], config.WEEKLY_MA_PERIODS):
        ma_d  = mas.get(period, {})
        above = ma_d.get("above")
        diff  = ma_d.get("pct_diff")
        with col:
            metric_card(
                f"{period}W MA",
                _fmt_btc(ma_d.get("ma")),
                f"{'Above' if above else 'Below'} ({diff:+.2f}%)" if diff is not None else "",
                change_positive=above,
            )
    with tc4:
        rsi_zone = "Momentum (50-70)" if (rsi and 50 <= rsi <= 70) else \
                   ("Overbought >75" if (rsi and rsi > 75) else \
                   ("Weak <40" if (rsi and rsi < 40) else "Neutral"))
        metric_card("RSI (14W)", _fmt(rsi, 1), rsi_zone,
                    change_positive=(rsi and 50 <= rsi <= 70))
    with tc5:
        macd_bull  = macd.get("bullish")
        macd_cross = macd.get("crossing_up")
        macd_label = "Bullish Cross!" if macd_cross else ("Above 0" if macd_bull else "Below 0")
        metric_card("MACD Weekly", _fmt(macd.get("histogram"), 0), macd_label, change_positive=macd_bull)

    # Price + MA chart
    fig_btc = charts.chart_btc_price_ma(data["prices"], mas)
    st.plotly_chart(fig_btc, use_container_width=True, config={"displayModeBar": False})

    rsi_col, macd_col = st.columns(2)
    with rsi_col:
        fig_rsi = charts.chart_rsi(data["prices"])
        st.plotly_chart(fig_rsi, use_container_width=True, config={"displayModeBar": False})
    with macd_col:
        fig_macd = charts.chart_macd(data["prices"])
        st.plotly_chart(fig_macd, use_container_width=True, config={"displayModeBar": False})

    # Bollinger Bands
    bb_data = tech.get("bollinger_bands", {})
    if bb_data:
        fig_bb = charts.chart_bollinger_bands(data["prices"], bb_data)
        st.plotly_chart(fig_bb, use_container_width=True, config={"displayModeBar": False})

        bb1, bb2, bb3, bb4 = st.columns(4)
        with bb1:
            metric_card("BB Upper (20W,2σ)", _fmt_btc(bb_data.get("upper")), "")
        with bb2:
            metric_card("BB Middle (20W MA)", _fmt_btc(bb_data.get("middle")), "")
        with bb3:
            metric_card("BB Lower (20W,2σ)", _fmt_btc(bb_data.get("lower")), "")
        with bb4:
            pct_b   = bb_data.get("pct_b")
            bw      = bb_data.get("bandwidth")
            bw_str  = f"BW: {bw:.1f}%" if bw else ""
            ob_zone = bb_data.get("overbought")
            os_zone = bb_data.get("oversold")
            bb_zone = ("Near/Above Upper" if ob_zone else ("Near/Below Lower" if os_zone else "Mid-range"))
            metric_card("%B Position", f"{pct_b:.1f}%" if pct_b is not None else "N/A",
                        f"{bb_zone} | {bw_str}", change_positive=os_zone if os_zone else (not ob_zone if ob_zone is not None else None))

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 5.5: KEY PRICE LEVELS & VOLATILITY PARAMETERS
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Key Price Levels & Volatility Parameters")
    st.caption(
        "Essential trade reference levels: ATH, 52-week range, psychological levels, "
        "daily ATR(14) for stop sizing, and weekly candle range."
    )

    kl = ind.get("key_levels", {})
    if kl:
        kp1, kp2, kp3, kp4, kp5 = st.columns(5)
        with kp1:
            ath_d = kl.get("ath_dist_pct")
            metric_card(
                "All-Time High",
                _fmt_btc(kl.get("ath")),
                f"{ath_d:+.1f}% from current" if ath_d is not None else "",
                change_positive=None,
            )
        with kp2:
            metric_card(
                "52-Week High",
                _fmt_btc(kl.get("w52_high")),
                f"{kl.get('w52_high_dist', 0):+.1f}% from current",
                change_positive=None,
            )
        with kp3:
            metric_card(
                "52-Week Low",
                _fmt_btc(kl.get("w52_low")),
                f"{kl.get('w52_low_dist', 0):+.1f}% from current",
                change_positive=None,
            )
        with kp4:
            atr   = kl.get("daily_atr")
            atr_p = round(atr / kl["current_price"] * 100, 2) if atr and kl.get("current_price") else None
            metric_card(
                "Daily ATR(14)",
                _fmt_btc(atr) if atr else "N/A",
                f"{atr_p:.2f}% of price — use for stop sizing" if atr_p else "",
                change_positive=None,
            )
        with kp5:
            wk_r = kl.get("weekly_range_pct")
            metric_card(
                "Weekly Candle Range",
                f"{wk_r:.2f}%" if wk_r else "N/A",
                f"H: {_fmt_btc(kl.get('weekly_high'))}  L: {_fmt_btc(kl.get('weekly_low'))}",
                change_positive=None,
            )

        # Psychological levels table
        above = kl.get("nearest_above", [])
        below = kl.get("nearest_below", [])
        current_price = kl.get("current_price", 0)

        psych_cols = st.columns(len(above) + 1 + len(below))
        col_idx = 0
        for item in sorted(above, key=lambda x: -x["level"]):
            with psych_cols[col_idx]:
                metric_card(
                    f"${item['level']:,} (Resistance)",
                    f"{item['dist_pct']:+.1f}%",
                    "Above current",
                    change_positive=None,
                )
            col_idx += 1
        with psych_cols[col_idx]:
            metric_card("Current BTC", _fmt_btc(current_price), "▲ Resistance above | ▼ Support below", change_positive=None)
        col_idx += 1
        for item in sorted(below, key=lambda x: -x["level"]):
            with psych_cols[col_idx]:
                metric_card(
                    f"${item['level']:,} (Support)",
                    f"{item['dist_pct']:+.1f}%",
                    "Below current",
                    change_positive=None,
                )
            col_idx += 1

        # Distance chart
        fig_kl = charts.chart_key_levels_distance(kl)
        st.plotly_chart(fig_kl, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 6: CROSS-ASSET PANEL
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### Cross-Asset")
    st.caption(
        "BTC is a risk-on asset. Rising SPX/QQQ = Bullish BTC. Rising VIX = Bearish BTC. "
        "Falling DXY = Bullish BTC."
    )

    cross = ind.get("cross_asset", {})

    xc1, xc2, xc3, xc4, xc5 = st.columns(5)
    cross_items = [
        (xc1, "VIX",       cross.get("vix",           {}), True),   # rising VIX = bearish BTC
        (xc2, "S&P 500",   cross.get("spx",           {}), False),  # rising SPX = bullish BTC
        (xc3, "QQQ",       cross.get("qqq",           {}), False),  # rising QQQ = bullish BTC
        (xc4, "EUR/USD",   cross.get("eurusd",        {}), False),  # rising EURUSD = bullish BTC (weak USD)
        (xc5, "BTC/Gold",  cross.get("btc_gold_ratio",{}), False),  # rising = BTC outperforming gold
    ]

    for col, label, d, invert_pos in cross_items:
        val = d.get("value")
        chg = d.get("weekly_chg")
        arrow_str, is_pos = _arrow(chg)
        # BTC-bullish direction
        if is_pos is None:
            btc_pos = None
        elif label == "VIX":
            btc_pos = not is_pos    # rising VIX = bearish BTC
        else:
            btc_pos = is_pos        # all others: rising = bullish BTC
        with col:
            metric_card(label, _fmt(val, 4 if "USD" in label else 2),
                        f"{arrow_str} wk", change_positive=btc_pos)

    fig_cross = charts.chart_cross_asset(data["prices"])
    st.plotly_chart(fig_cross, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 7: BTC ON-CHAIN & HALVING CYCLE
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### ₿ On-Chain & Halving Cycle")
    st.caption(
        "BTC halving (every ~4 years) cuts new supply in half — historically the single biggest "
        "structural catalyst for BTC bull markets. On-chain data from blockchain.com (no API key needed)."
    )

    btc_spec  = ind.get("btc_specific", {})
    halving   = btc_spec.get("halving", {})
    onchain   = btc_spec.get("onchain", {})
    dominance = btc_spec.get("dominance")

    # ── Halving cycle progress bar ────────────────────────────────────
    fig_halving = charts.chart_halving_cycle(halving)
    st.plotly_chart(fig_halving, use_container_width=True, config={"displayModeBar": False})

    # ── Metric cards row ─────────────────────────────────────────────
    hc1, hc2, hc3, hc4 = st.columns(4)
    with hc1:
        phase = halving.get("phase", "N/A")
        months_sin = halving.get("months_since")
        phase_colors = {
            "Early Bull":  "bull-text",
            "Peak Risk":   "neut-text",
            "Bear Market": "bear-text",
            "Pre-Halving": "neut-text",
        }
        phase_cls = phase_colors.get(phase, "neut-text")
        metric_card(
            "Halving Cycle Phase",
            phase,
            f"{months_sin:.0f} months post-halving" if months_sin is not None else "",
            change_positive=(phase in ("Early Bull", "Pre-Halving")),
        )
    with hc2:
        days_to = halving.get("days_to_next")
        next_h  = halving.get("next_halving", "")
        metric_card(
            "Next Halving",
            f"{days_to:,} days" if days_to is not None else "N/A",
            next_h,
            change_positive=None,
        )
    with hc3:
        hr_data   = onchain.get("hash_rate", {})
        hr_val    = hr_data.get("value")
        hr_trend  = hr_data.get("trend_pct")
        hr_rising = hr_data.get("rising")
        hr_trend_str = (
            f"{'▲' if hr_trend and hr_trend > 0 else '▼'} {abs(hr_trend):.1f}% (4W)"
            if hr_trend is not None else ""
        )
        metric_card(
            "Network Hash Rate",
            _fmt(hr_val, 1, " EH/s") if hr_val else "N/A",
            hr_trend_str,
            change_positive=hr_rising,
        )
    with hc4:
        metric_card(
            "BTC Market Dominance",
            _fmt(dominance, 1, "%") if dominance else "N/A",
            "Rising = BTC leading altcoins",
            change_positive=dominance and dominance > 50 if dominance else None,
        )

    # ── On-chain charts ───────────────────────────────────────────────
    oc1, oc2 = st.columns(2)
    with oc1:
        fig_hr = charts.chart_hashrate(onchain)
        st.plotly_chart(fig_hr, use_container_width=True, config={"displayModeBar": False})
    with oc2:
        fig_mr = charts.chart_miner_revenue(onchain)
        st.plotly_chart(fig_mr, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # SECTION 8: ICT TRADE IDEAS
    # ════════════════════════════════════════════════════════════════════
    st.markdown("### ICT Trade Ideas (Daily)")
    st.caption(
        "Educational ICT analysis only — not financial advice. "
        "Concepts applied: Market Structure · Order Blocks · Fair Value Gaps · Fibonacci OTE (0.618–0.705) · Key Levels"
    )

    monthly_df_ict = data.get("monthly_btc", pd.DataFrame())
    weekly_df_ict  = data.get("weekly_btc",  pd.DataFrame())
    daily_df_ict   = data.get("daily_btc",   pd.DataFrame())

    if monthly_df_ict.empty or weekly_df_ict.empty or daily_df_ict.empty:
        st.warning("ICT data unavailable — price DataFrames not loaded. Click Refresh Data.")
    else:
        with st.spinner("Running ICT analysis..."):
            ict_trades     = ict_analysis.generate_ict_trades(
                monthly_df_ict, weekly_df_ict, daily_df_ict, bias["score"])
            ict_key_levels = ict_analysis.get_key_levels(monthly_df_ict, weekly_df_ict)
            sh, sl, _      = ict_analysis._find_major_swing(daily_df_ict, lookback_bars=30)
            if sh - sl < float(daily_df_ict["Close"].iloc[-1]) * 0.01:
                sh, sl, _ = ict_analysis._find_major_swing(daily_df_ict, lookback_bars=60)
            ict_fib        = ict_analysis.calc_fibonacci_levels(sh, sl)
            all_fvgs       = (
                [f for f in ict_analysis.find_fvgs(weekly_df_ict) if not f["filled"]] +
                [f for f in ict_analysis.find_fvgs(daily_df_ict)  if not f["filled"]]
            )
            all_obs        = (
                [o for o in ict_analysis.find_order_blocks(weekly_df_ict) if o["valid"]] +
                [o for o in ict_analysis.find_order_blocks(daily_df_ict)  if o["valid"]]
            )

        # ── Key levels summary row ─────────────────────────────────────
        kl = ict_key_levels
        kl1, kl2, kl3, kl4 = st.columns(4)
        with kl1:
            metric_card("Prev Month High (PMH)", _fmt_btc(kl.get("PMH")))
        with kl2:
            metric_card("Prev Month Low (PML)",  _fmt_btc(kl.get("PML")))
        with kl3:
            metric_card("Prev Week High (PWH)",  _fmt_btc(kl.get("PWH")))
        with kl4:
            metric_card("Prev Week Low (PWL)",   _fmt_btc(kl.get("PWL")))

        # Fibonacci summary
        if ict_fib:
            fifty = ict_fib.get(0.5)
            ote_l = ict_fib.get(0.618)
            ote_h = ict_fib.get(0.705)
            current_btc = ind.get("btc_price")
            zone_label = ""
            if current_btc and fifty:
                zone_label = "🔵 Discount Zone" if current_btc < fifty else "🔴 Premium Zone"
            st.markdown(
                f"<div style='font-size:12px; color:#888; margin: 4px 0 12px 0;'>"
                f"Swing: ${_fmt(ict_fib.get('swing_low'), 0)} → ${_fmt(ict_fib.get('swing_high'), 0)} &nbsp;|&nbsp; "
                f"50% (mid): <strong style='color:#FFD740;'>${_fmt(fifty, 0)}</strong> &nbsp;|&nbsp; "
                f"OTE Zone: ${_fmt(ote_h, 0)} – ${_fmt(ote_l, 0)} &nbsp;|&nbsp; {zone_label}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── 3 Trade Cards ─────────────────────────────────────────────
        tc1, tc2, tc3 = st.columns(3)
        trade_titles = [
            "Trade 1 — Primary Trend",
            "Trade 2 — OTE Retracement",
            "Trade 3 — Liquidity Hunt",
        ]

        for col, trade, title in zip([tc1, tc2, tc3], ict_trades, trade_titles):
            d    = trade["direction"]
            conf = trade["confidence"]
            is_low = (conf == "LOW")

            badge_color = "#00C853" if d == "LONG" else ("#D50000" if d == "SHORT" else "#FFD740")
            conf_color  = (
                "#00C853" if conf == "HIGH"
                else ("#FFD740" if conf == "MEDIUM"
                      else "#888888")
            )
            card_opacity = "0.55" if is_low else "1.0"
            card_border  = "1px solid #444" if is_low else ""
            card_style   = (f"opacity:{card_opacity}; border:{card_border};" if is_low else "")

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
                        <b>Entry:</b> &nbsp;${_fmt(trade['entry'], 0)}<br>
                        <b>Stop: </b> &nbsp;${_fmt(trade['stop'],  0)}<br>
                        <b>TP1:  </b> &nbsp;${_fmt(trade['target1'], 0)}
                            <span style="color:#888; font-size:11px;">&nbsp;(R:R {_fmt(trade['rr1'], 2)})</span><br>
                        <b>TP2:  </b> &nbsp;${_fmt(trade['target2'], 0)}
                            <span style="color:#888; font-size:11px;">&nbsp;(R:R {_fmt(trade['rr2'], 2)})</span>
                    </div>
                    <div style="margin:8px 0 4px; font-size:11px;">
                        Confidence: <span style="color:{conf_color}; font-weight:700;">{conf}</span>
                        &nbsp;|&nbsp; TF: <span style="color:#888;">{trade['timeframe']}</span>
                    </div>
                    <div style="font-size:11px; color:#aaa; line-height:1.5; border-top:1px solid #2A2D35; padding-top:6px;">
                        {trade['rationale']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if trade.get("key_levels_used"):
                    st.caption("📌 " + " · ".join(trade["key_levels_used"]))

        # ── Position Sizing Panel ─────────────────────────────────────
        st.markdown("#### Trade Execution Parameters")
        st.caption(
            "Position sizes calculated from stop distance at 1% and 2% account risk. "
            "Daily ATR used to assess stop quality. Adjust to your account size."
        )

        daily_atr_val = ind.get("key_levels", {}).get("daily_atr")
        current_btc   = ind.get("btc_price")

        ps_cols = st.columns(len(ict_trades))
        for col, trade in zip(ps_cols, ict_trades):
            if trade["direction"] == "WAIT":
                with col:
                    st.markdown("<div class='metric-card' style='opacity:0.5;'><div class='metric-label'>WAIT — No Setup</div></div>",
                                unsafe_allow_html=True)
                continue

            entry = trade.get("entry") or 0
            stop  = trade.get("stop")  or 0
            if entry == 0 or stop == 0:
                continue

            stop_dist_usd = abs(entry - stop)
            stop_dist_pct = round(stop_dist_usd / entry * 100, 2) if entry > 0 else None

            # Multiples of ATR
            atr_mult = round(stop_dist_usd / daily_atr_val, 2) if daily_atr_val and daily_atr_val > 0 else None

            # Position sizes (contracts in BTC) at 1% and 2% risk
            def _pos_size(acct_usd, risk_pct):
                if stop_dist_usd == 0:
                    return None
                risk_usd = acct_usd * risk_pct / 100
                btc_qty  = risk_usd / stop_dist_usd
                return round(btc_qty, 4)

            ps_10k_1 = _pos_size(10_000, 1)
            ps_10k_2 = _pos_size(10_000, 2)
            ps_50k_1 = _pos_size(50_000, 1)

            rr1 = trade.get("rr1") or 0
            rr2 = trade.get("rr2") or 0

            d_color = "#00C853" if trade["direction"] == "LONG" else "#D50000"

            atr_str  = f"{daily_atr_val:,.0f}" if daily_atr_val else "N/A"
            atr_mult_str = f"{atr_mult:.1f}" if atr_mult is not None else "N/A"
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size:11px; color:#888; margin-bottom:6px;">
                        Trade {trade['id']} — Execution Parameters
                    </div>
                    <div style="font-size:12px; color:#FAFAFA; line-height:2.0;">
                        <b>Stop Dist:</b> &nbsp;${stop_dist_usd:,.0f}
                            <span style="color:#888; font-size:11px;">&nbsp;({stop_dist_pct:+.2f}%)</span><br>
                        <b>ATR mult:</b> &nbsp;{atr_mult_str}&times; ATR(14)
                            <span style="color:#888; font-size:11px;">&nbsp;(ATR&#8776;${atr_str})</span><br>
                        <div style="border-top:1px solid #2A2D35; margin: 6px 0;"></div>
                        <b>Position size (BTC) @ 1% risk</b><br>
                        &nbsp;$10K acct: <span style="color:{d_color};">{ps_10k_1} BTC</span><br>
                        &nbsp;$50K acct: <span style="color:{d_color};">{ps_50k_1} BTC</span><br>
                        &nbsp;$10K @ 2%: <span style="color:{d_color};">{ps_10k_2} BTC</span><br>
                        <div style="border-top:1px solid #2A2D35; margin: 6px 0;"></div>
                        <b>R:R Targets</b><br>
                        &nbsp;TP1: <span style="color:#69F0AE;">{rr1:.2f}R</span>
                            &nbsp;TP2: <span style="color:#00C853;">{rr2:.2f}R</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<div style="margin-top:6px; font-size:11px; color:#666;">'
                    '⚠️ Position sizes are illustrative only. Always size based on your own risk tolerance, '
                    'account type (spot vs leveraged), and market liquidity. Not financial advice.'
                    '</div>', unsafe_allow_html=True)

        # ── ICT Chart ─────────────────────────────────────────────────
        fig_ict = charts.chart_ict_levels(
            daily_df=daily_df_ict,
            weekly_df=weekly_df_ict,
            trades=ict_trades,
            key_levels=ict_key_levels,
            fvgs=all_fvgs,
            obs=all_obs,
            fib=ict_fib,
        )
        st.plotly_chart(fig_ict, use_container_width=True, config={"displayModeBar": False})

    # ════════════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════════════
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.caption(
        "Data: Yahoo Finance (prices, ETFs) · FRED API (macro) · CFTC (CME BTC COT) · "
        "Alternative.me (Fear & Greed) — all free sources. "
        "This dashboard is for informational purposes only. Not financial advice."
    )


if __name__ == "__main__":
    main()
