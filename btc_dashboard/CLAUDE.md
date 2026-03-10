# CLAUDE.md — Bitcoin Weekly Bias Dashboard

## Project Overview

A Streamlit dashboard that computes a multi-factor directional bias score for Bitcoin (BTC/USD)
using macro, sentiment, technical, and cross-asset indicators, augmented with an ICT
(Inner Circle Trader) structural analysis engine. Data is sourced live from Yahoo Finance,
FRED, CFTC, and the Alternative.me Fear & Greed API.

---

## Setup

```bash
pip install -r requirements.txt          # install dependencies
cp .env.example .env                     # create env file
# edit .env and add your FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
# Fear & Greed Index is free with no API key required
streamlit run app.py                     # launch dashboard
python -m py_compile *.py               # validate syntax (no runtime needed)
```

---

## Architecture

Data flows in one direction: **config → data → indicators → scoring → charts → app**

| File | Responsibility |
|---|---|
| `config.py` | All constants: tickers, FRED series IDs, scoring weights, thresholds |
| `data_fetcher.py` | External API calls — yfinance, FRED REST, CFTC COT, Fear & Greed |
| `indicators.py` | Pure technical calculations — MAs, RSI, MACD, ETF flows, Fear & Greed |
| `scoring.py` | Weighted multi-factor bias score (returns float in `[-1.0, +1.0]`) |
| `charts.py` | Plotly figure builders — one function per chart |
| `ict_analysis.py` | ICT engine: swing detection, order blocks, FVGs, OTE, trade ideas |
| `app.py` | Streamlit UI entry point — orchestrates all modules, handles caching |

---

## Data Sources

| Source | Library / Method | What it provides |
|---|---|---|
| Yahoo Finance | `yfinance` | OHLCV for tickers (weekly / daily / monthly) |
| FRED | Direct REST API | Real yields, CPI, PCE, treasury yields, fed funds, M2 |
| CFTC | Direct REST API | COT disaggregated futures — CME Bitcoin contract `133741` |
| Alternative.me | Direct REST API | Crypto Fear & Greed Index (no API key required) |

- FRED requires a free API key stored in `.env` as `FRED_API_KEY`.
- Fear & Greed Index: no key required — `https://api.alternative.me/fng/`
- All tickers are defined in `config.py → TICKERS`.
- FRED series IDs are in `config.py → FRED_SERIES`.

---

## Scoring Model

Bias score: **-1.0 (Strong Bearish) → +1.0 (Strong Bullish)**

| Category | Weight | Key Difference from Gold |
|---|---|---|
| Macro | 30% | Same drivers (DXY, real yields, Fed policy) |
| Sentiment | 35% | Fear & Greed + BTC ETF flows replace Gold COT/ETF |
| Technical | 25% | Same (MA, RSI, MACD) on BTC price |
| Cross-Asset | 10% | VIX=BEARISH, SPX=BULLISH (opposite of gold!) |

### BTC vs Gold scoring differences
- **VIX rising** = BEARISH BTC (risk-off asset vs gold's risk-off haven)
- **SPX rising** = BULLISH BTC (positive risk correlation)
- **Fear & Greed extreme fear (<20)** = contrarian BULLISH
- **Fear & Greed extreme greed (>80)** = contrarian BEARISH

All weights and thresholds live exclusively in `config.py`. Never hardcode them in logic files.

---

## Coding Conventions

- **Language:** Python 3.10+ (use `X | Y` union syntax, not `Optional[X]`)
- **Style:** `snake_case` for all names; 4-space indent; max ~100 chars per line
- **Function prefixes:**
  - `fetch_*` — data retrieval (network I/O)
  - `calc_*` — pure calculations
  - `chart_*` — returns a Plotly `Figure`
  - `score_*` — returns a float in `[-1.0, +1.0]`
- **No magic numbers** — every constant goes in `config.py` with a comment
- **Type hints** — required on all public function signatures
- **Docstrings** — one-line summary on every public function
- **Error handling** — wrap every API call in try/except; return an empty `pd.DataFrame()` or `None` on failure; never raise to the UI
- **Caching** — decorate every data-fetching function with `@st.cache_data(ttl=3600)`

---

## Constraints

- **Never commit `.env`** — it is in `.gitignore`; use `.env.example` for documentation
- **No hardcoded API keys or tickers** — everything goes through `config.py`
- **No database** — all data is fetched fresh and cached by Streamlit (`ttl=3600`)
- **No external state** — functions must be stateless and side-effect-free
- **Weight changes require a comment** — if scoring weights change, update both `config.py`
  and the comment block above the weight dict explaining the rationale
