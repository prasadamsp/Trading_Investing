# CLAUDE.md — Gold Weekly Bias Dashboard

## Project Overview

A Streamlit dashboard that computes a multi-factor directional bias score for gold (XAU/USD)
using macro, sentiment, technical, and cross-asset indicators, augmented with an ICT
(Inner Circle Trader) structural analysis engine. Data is sourced live from Yahoo Finance,
FRED, and CFTC.

---

## Setup

```bash
pip install -r requirements.txt          # install dependencies
cp .env.example .env                     # create env file
# edit .env and add your FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
streamlit run app.py                     # launch dashboard
python -m py_compile *.py               # validate syntax (no runtime needed)
```

---

## Architecture

Data flows in one direction: **config → data → indicators → scoring → charts → app**

| File | Responsibility |
|---|---|
| `config.py` | All constants: tickers, FRED series IDs, scoring weights, thresholds |
| `data_fetcher.py` | External API calls — yfinance, FRED REST, CFTC COT |
| `indicators.py` | Pure technical calculations — MAs, RSI, MACD, ETF flows |
| `scoring.py` | Weighted multi-factor bias score (returns float in `[-1.0, +1.0]`) |
| `charts.py` | Plotly figure builders — one function per chart |
| `ict_analysis.py` | ICT engine: swing detection, order blocks, FVGs, OTE, trade ideas |
| `app.py` | Streamlit UI entry point — orchestrates all modules, handles caching |

---

## Data Sources

| Source | Library / Method | What it provides |
|---|---|---|
| Yahoo Finance | `yfinance` | OHLCV for 16 tickers (weekly / daily / monthly) |
| FRED | Direct REST API | Real yields, CPI, PCE, treasury yields, fed funds |
| CFTC | Direct REST API | COT disaggregated futures — gold contract `088691` |

- FRED requires a free API key stored in `.env` as `FRED_API_KEY`.
- All 16 tracked tickers are defined in `config.py → TICKERS`.
- FRED series IDs are in `config.py → FRED_SERIES`.

---

## Scoring Model

Bias score: **-1.0 (Strong Bearish) → +1.0 (Strong Bullish)**

| Category | Weight |
|---|---|
| Macro | 35% |
| Sentiment | 30% |
| Technical | 25% |
| Cross-Asset | 10% |

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

## Testing

```bash
python test_ict.py       # ICT module smoke test (uses live data)
python test_ict2.py      # additional ICT assertions
python test_live.py      # end-to-end live data integration test
```

No formal framework is configured yet. When adding pytest, place tests in a `tests/`
directory and mirror the module structure.

---

## Constraints

- **Never commit `.env`** — it is in `.gitignore`; use `.env.example` for documentation
- **No hardcoded API keys or tickers** — everything goes through `config.py`
- **No database** — all data is fetched fresh and cached by Streamlit (`ttl=3600`)
- **No external state** — functions must be stateless and side-effect-free
- **Weight changes require a comment** — if scoring weights change, update both `config.py`
  and the comment block above the weight dict explaining the rationale
