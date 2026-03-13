# =============================================================================
# Trade Ideas Dashboard — Streamlit App
# =============================================================================
"""
Unified intraday-to-intra-week trade ideas dashboard combining:
  - Stan Weinstein Stage Analysis
  - Larry Williams COT Commercial Hedger scoring
  - ICT concepts (OB, FVG, OTE, killzones) on 4H timeframe
  - Mark Douglas A+/A/B grade system

Run: streamlit run app.py
"""
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import config
import data_fetcher
import indicators as ind
import ict_engine
import trade_generator
import charts

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=config.PAGE_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark theme CSS — all text colours set explicitly for readability
st.markdown("""
<style>
    .main { background-color: #0E1117; }
    .block-container { padding-top: 1rem; }

    .grade-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.9em;
        font-family: monospace;
        margin-right: 8px;
        letter-spacing: 0.05em;
    }
    .stage-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 0.78em;
        font-weight: bold;
        font-family: monospace;
    }

    /* ---- Trade card container ---- */
    .trade-card {
        background: #1C2128;
        border: 1px solid #444C56;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 14px;
        color: #E6EDF3;
    }

    /* Header row: asset name + timestamp */
    .tc-header {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
        font-size: 1.05em;
    }
    .tc-asset {
        color: #FFFFFF;
        font-weight: 700;
        font-size: 1.1em;
        margin-right: 10px;
    }
    .tc-timestamp {
        color: #8B949E;
        font-size: 0.82em;
    }

    /* Price grid */
    .tc-grid {
        display: grid;
        grid-template-columns: repeat(4, auto);
        gap: 6px 24px;
        font-family: monospace;
        margin-bottom: 10px;
    }
    .tc-label {
        color: #8B949E;
        font-size: 0.8em;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        display: block;
    }
    .tc-value {
        color: #E6EDF3;
        font-size: 1.0em;
        font-weight: 600;
        display: block;
    }
    .tc-value-entry  { color: #58A6FF; }
    .tc-value-stop   { color: #F85149; }
    .tc-value-target { color: #3FB950; }

    /* Meta row (RR, points, session) */
    .tc-meta {
        font-family: monospace;
        font-size: 0.88em;
        color: #C9D1D9;
        margin-bottom: 10px;
        line-height: 1.9;
    }
    .tc-meta b { color: #E6EDF3; }

    /* Confluence chips */
    .factor-chip {
        display: inline-block;
        padding: 2px 9px;
        border-radius: 10px;
        font-size: 0.78em;
        font-family: monospace;
        font-weight: 600;
        margin: 2px 3px 2px 0;
        color: #FFFFFF;
        background: #238636;
        border: 1px solid #2EA043;
    }

    /* Rationale */
    .tc-rationale {
        font-size: 0.85em;
        color: #C9D1D9;
        font-style: italic;
        margin-top: 8px;
        line-height: 1.5;
        border-top: 1px solid #30363D;
        padding-top: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=config.REFRESH_TTL_SECS, show_spinner=False)
def load_data() -> dict:
    return data_fetcher.fetch_all_data()


@st.cache_data(ttl=config.REFRESH_TTL_SECS, show_spinner=False)
def load_all_indicators(data: dict) -> dict:
    result = {}
    for asset_key in config.ASSETS:
        result[asset_key] = ind.build_indicators(asset_key, data)
    return result


@st.cache_data(ttl=config.REFRESH_TTL_SECS, show_spinner=False)
def load_all_ict(data: dict) -> dict:
    result = {}
    for asset_key in config.ASSETS:
        result[asset_key] = ict_engine.build_ict_signals(asset_key, data)
    return result


# ---------------------------------------------------------------------------
# Helper renderers
# ---------------------------------------------------------------------------

def _grade_badge(grade: str) -> str:
    color = config.GRADE_COLORS.get(grade, "#999")
    return (f'<span class="grade-badge" style="background:{color}20;'
            f'border:1px solid {color};color:{color}">{grade}</span>')


def _stage_badge(stage: int | None) -> str:
    if stage is None:
        return '<span class="stage-badge" style="background:#333;color:#999">?</span>'
    color = config.STAGE_COLORS.get(stage, "#FFD740")
    label = config.STAGE_LABELS.get(stage, f"S{stage}")
    return (f'<span class="stage-badge" style="background:{color}25;'
            f'border:1px solid {color};color:{color}">{label}</span>')


def _direction_icon(direction: str) -> str:
    return "🟢" if direction == "LONG" else "🔴"


def _fmt_price(v: float, asset_key: str) -> str:
    pip = config.ASSETS[asset_key].get("pip", 0.01)
    if pip <= 0.0001:
        return f"{v:.5f}"
    elif pip <= 0.01:
        return f"{v:.4f}"
    elif pip <= 0.1:
        return f"{v:.2f}"
    return f"{v:.2f}"


def _confluence_chips(factors: dict) -> str:
    label_map = {
        "weinstein_stage": "Weinstein",
        "cot_commercial":  "COT Comm",
        "williams_r":      "W%R",
        "ict_ote":         "OTE",
        "order_block":     "OB",
        "fvg":             "FVG",
        "killzone":        "Killzone",
        "daily_bias":      "Daily Bias",
    }
    parts = []
    for key, (pts, active) in factors.items():
        label = label_map.get(key, key)
        if active:
            parts.append(
                f'<span class="factor-chip">{label} +{pts}</span>'
            )
        else:
            parts.append(
                f'<span style="display:inline-block;padding:2px 9px;border-radius:10px;'
                f'font-size:0.78em;font-family:monospace;font-weight:500;margin:2px 3px 2px 0;'
                f'color:#555D65;background:#21262D;border:1px solid #30363D">{label}</span>'
            )
    return " ".join(parts)


def _render_trade_card(idea: dict, account_size: float, risk_pct: float):
    asset_key = idea["asset_key"]
    fmt = lambda v: _fmt_price(v, asset_key)

    pos = trade_generator.calc_position_size_for_idea(idea, account_size, risk_pct)

    kz = idea.get("killzone", {})
    kz_text = ""
    if kz.get("active"):
        kz_text = f"🔥 **{kz['session_name']}** (active NOW)"
    elif kz.get("next_session"):
        h = kz["minutes_to_next"] // 60
        m = kz["minutes_to_next"] % 60
        kz_text = f"Next: {kz['next_session']} in {h}h {m:02d}m"

    dir_color = "#3FB950" if idea["direction"] == "LONG" else "#F85149"

    st.markdown(f"""
<div class="trade-card">

  <!-- Header -->
  <div class="tc-header">
    {_grade_badge(idea["grade"])}
    <span style="color:{dir_color};font-weight:700;font-size:1.05em;margin-right:8px">
      {idea["direction"]}
    </span>
    <span class="tc-asset">{idea["asset_name"]}</span>
    <span class="tc-timestamp">{idea["generated_at"]}</span>
  </div>

  <!-- Price grid -->
  <div class="tc-grid">
    <div>
      <span class="tc-label">Entry</span>
      <span class="tc-value tc-value-entry">{fmt(idea["entry"])}</span>
    </div>
    <div>
      <span class="tc-label">Stop</span>
      <span class="tc-value tc-value-stop">{fmt(idea["stop"])}</span>
    </div>
    <div>
      <span class="tc-label">Target 1</span>
      <span class="tc-value tc-value-target">{fmt(idea["target1"])}</span>
    </div>
    <div>
      <span class="tc-label">Target 2</span>
      <span class="tc-value tc-value-target">{fmt(idea["target2"])}</span>
    </div>
  </div>

  <!-- Meta row -->
  <div class="tc-meta">
    <b>RR1:</b> 1:{idea["rr1"]} &nbsp;&nbsp;
    <b>RR2:</b> 1:{idea["rr2"]} &nbsp;&nbsp;
    <b>Confluence:</b> {idea["points"]}/10 pts &nbsp;&nbsp;
    <b>ATR(4H):</b> {f'{idea["atr_4h"]:.4f}' if idea.get("atr_4h") else "—"}<br>
    <b>Session:</b> {kz_text or "Outside killzone"} &nbsp;&nbsp;
    <b>Position:</b> {pos["units"]:,} units &nbsp;|&nbsp;
    Risk <span style="color:#F85149">${pos["risk_amount"]:.0f}</span> ({risk_pct:.1f}%)
  </div>

  <!-- Confluence chips -->
  <div style="margin-bottom:10px">{_confluence_chips(idea["factors"])}</div>

  <!-- Rationale -->
  <div class="tc-rationale">{idea["rationale"]}</div>

</div>
""", unsafe_allow_html=True)

    # Mini-chart expander
    with st.expander("View 4H Chart", expanded=False):
        df_4h = st.session_state.get("data", {}).get("4h", {}).get(asset_key, pd.DataFrame())
        if not df_4h.empty:
            st.plotly_chart(
                charts.chart_trade_card(df_4h, idea, height=380),
                use_container_width=True,
                key=f"card_chart_{asset_key}_{idea['direction']}",
            )
        else:
            st.caption("4H data not available for chart.")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> dict:
    st.sidebar.title("Filters & Settings")

    st.sidebar.subheader("Trade Filters")
    asset_options = ["All"] + [v["name"] for v in config.ASSETS.values()]
    selected_asset = st.sidebar.selectbox("Asset", asset_options, index=0)

    direction_options = ["Both", "Long Only", "Short Only"]
    selected_dir = st.sidebar.selectbox("Direction", direction_options, index=0)

    grade_options = ["A+ only", "A+ and A", "A+, A, and B"]
    selected_grade = st.sidebar.selectbox("Minimum Grade", grade_options, index=2)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Risk Calculator")
    account_size = st.sidebar.number_input(
        "Account Size ($)", min_value=100, max_value=10_000_000,
        value=config.DEFAULT_ACCOUNT_SIZE, step=500,
    )
    risk_pct = st.sidebar.number_input(
        "Risk per Trade (%)", min_value=0.1, max_value=10.0,
        value=config.DEFAULT_RISK_PCT, step=0.1,
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    fetched_at = st.session_state.get("fetched_at")
    if fetched_at:
        st.sidebar.caption(f"Last updated: {fetched_at.strftime('%Y-%m-%d %H:%M')}")

    return {
        "selected_asset": selected_asset,
        "direction":      selected_dir,
        "min_grade":      selected_grade,
        "account_size":   account_size,
        "risk_pct":       risk_pct,
    }


def _filter_ideas(ideas: list[dict], filters: dict) -> list[dict]:
    grade_map = {
        "A+ only":        {"A+"},
        "A+ and A":       {"A+", "A"},
        "A+, A, and B":   {"A+", "A", "B"},
    }
    allowed_grades = grade_map.get(filters["min_grade"], {"A+", "A", "B"})

    filtered = [i for i in ideas if i["grade"] in allowed_grades]

    if filters["selected_asset"] != "All":
        filtered = [i for i in filtered if i["asset_name"] == filters["selected_asset"]]

    if filters["direction"] == "Long Only":
        filtered = [i for i in filtered if i["direction"] == "LONG"]
    elif filters["direction"] == "Short Only":
        filtered = [i for i in filtered if i["direction"] == "SHORT"]

    return filtered


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

def main():
    st.title("Trade Ideas Dashboard")
    st.caption("ICT · Larry Williams COT · Stan Weinstein Stage · Mark Douglas Grading")

    # ----- Load data -----
    with st.spinner("Fetching market data…"):
        data = load_data()

    st.session_state["data"]       = data
    st.session_state["fetched_at"] = data.get("fetched_at")

    with st.spinner("Computing indicators…"):
        all_indicators = load_all_indicators(data)
        all_ict        = load_all_ict(data)

    filters = render_sidebar()

    # ----- Section 1: Market Context Header -----
    st.markdown("## Market Context")
    header_cols = st.columns(len(config.ASSETS))

    for col, (asset_key, asset_cfg) in zip(header_cols, config.ASSETS.items()):
        ind_data  = all_indicators[asset_key]
        weinstein = ind_data["weinstein"]
        price     = ind_data.get("price")
        chg       = None

        daily_df  = data["daily"].get(asset_key, pd.DataFrame())
        if not daily_df.empty and "Close" in daily_df.columns and len(daily_df) >= 2:
            closes = daily_df["Close"].dropna()
            if len(closes) >= 2:
                chg = float((closes.iloc[-1] / closes.iloc[-2] - 1) * 100)

        stage = weinstein.get("stage")
        stage_color = config.STAGE_COLORS.get(stage, "#FFD740")
        stage_label = config.STAGE_LABELS.get(stage, "?")

        with col:
            price_str = f"{price:,.4f}" if price else "—"
            chg_str   = (f"+{chg:.2f}%" if chg and chg >= 0 else f"{chg:.2f}%") if chg else "—"
            chg_color = "#00C853" if (chg and chg >= 0) else "#D50000"

            st.markdown(f"""
<div style="text-align:center;padding:10px 8px;background:#1C2128;
            border-radius:6px;border:1px solid #444C56;margin-bottom:4px">
  <div style="font-size:0.88em;font-weight:700;color:#FFFFFF;margin-bottom:2px">{asset_cfg['name']}</div>
  <div style="font-size:1.05em;font-weight:700;color:#58A6FF;margin-bottom:2px">{price_str}</div>
  <div style="font-size:0.85em;font-weight:600;color:{chg_color};margin-bottom:4px">{chg_str}</div>
  <span style="display:inline-block;padding:2px 8px;border-radius:3px;font-size:0.72em;
               font-weight:700;font-family:monospace;
               background:{stage_color}30;border:1px solid {stage_color};color:{stage_color}">
    {stage_label}
  </span>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ----- Section 5: Session Timing (compact header bar) -----
    kz = ict_engine.get_killzone_status()
    col_time, col_session = st.columns([1, 3])
    with col_time:
        st.metric("UTC Time", kz["current_utc"])
    with col_session:
        if kz["active"]:
            st.success(f"Active Session: **{kz['session_name']}**")
        else:
            h = kz["minutes_to_next"] // 60 if kz["minutes_to_next"] else 0
            m = kz["minutes_to_next"] % 60  if kz["minutes_to_next"] else 0
            st.info(f"Next Session: **{kz['next_session']}** in {h}h {m:02d}m")

    st.markdown("---")

    # ----- Generate trade ideas -----
    with st.spinner("Generating trade ideas…"):
        all_ideas = trade_generator.generate_trade_ideas(data)

    # ----- Section 2: Trade Ideas Feed -----
    st.markdown("## Trade Ideas Feed")
    filtered = _filter_ideas(all_ideas, filters)

    if not filtered:
        st.warning("No trade ideas match the current filters. Try lowering the minimum grade or broadening asset/direction filters.")
    else:
        st.caption(f"Showing **{len(filtered)}** idea(s) | Total generated: {len(all_ideas)}")
        for idea in filtered:
            _render_trade_card(idea, filters["account_size"], filters["risk_pct"])

    st.markdown("---")

    # ----- Section 3: COT Smart Money Panel -----
    st.markdown("## COT Smart Money Panel (Larry Williams)")
    st.markdown(
        '> *"When commercials are at an extreme, trade with them -- they are the only ones who know the true value of the market."*  -- Larry Williams'
    )

    cot_table_df = charts.build_cot_table(all_indicators)
    st.dataframe(cot_table_df, use_container_width=True, hide_index=True)

    # COT charts — one per asset that has COT data
    cot_cols = st.columns(2)
    col_idx  = 0
    for asset_key, asset_cfg in config.ASSETS.items():
        cot_df = data["cot"].get(asset_key, pd.DataFrame())
        if cot_df.empty:
            continue
        cot_result = all_indicators[asset_key].get("cot", {})
        fig = charts.chart_cot_commercial(
            cot_df, asset_cfg["name"], cot_result, height=270,
        )
        with cot_cols[col_idx % 2]:
            st.plotly_chart(fig, use_container_width=True, key=f"cot_{asset_key}")
        col_idx += 1

    st.markdown("---")

    # ----- Section 4: Weinstein Stage Map -----
    st.markdown("## Weinstein Stage Map (Weekly)")
    weinstein_cols = st.columns(2)
    for idx, (asset_key, asset_cfg) in enumerate(config.ASSETS.items()):
        weekly_df = data["weekly"].get(asset_key, pd.DataFrame())
        weinstein = all_indicators[asset_key]["weinstein"]
        fig = charts.chart_weinstein_stage(weekly_df, asset_cfg["name"], weinstein, height=290)
        with weinstein_cols[idx % 2]:
            st.plotly_chart(fig, use_container_width=True, key=f"weinstein_{asset_key}")

    st.markdown("---")

    # ----- Section 5: Session Guide (detailed) -----
    st.markdown("## ICT Session Timing Guide")
    session_data = [
        {"Session": "London Killzone",  "UTC": "07:00–10:00", "EST": "02:00–05:00",
         "Best For": "Gold, GBP/USD, EUR/USD"},
        {"Session": "NY Open Killzone", "UTC": "12:00–15:00", "EST": "07:00–10:00",
         "Best For": "All assets, highest volume"},
        {"Session": "London Close",     "UTC": "15:00–17:00", "EST": "10:00–12:00",
         "Best For": "FX pairs, reversals"},
    ]
    st.table(pd.DataFrame(session_data))

    st.markdown("---")
    st.caption(
        "Disclaimer: Educational tool only. Not financial advice. "
        "All ideas generated algorithmically — always apply your own analysis before trading."
    )


if __name__ == "__main__":
    main()
