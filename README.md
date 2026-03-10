# Trading & Investing Dashboards

Three free, open-source weekly bias dashboards built with Python + Streamlit. Each scores directional bias from **-1.0 (Strong Bearish)** to **+1.0 (Strong Bullish)** using multiple independent factor groups.

---

## Dashboards

### 🛢 Oil Dashboard — WTI Crude Bias
`oil_dashboard/` · [Deploy on Streamlit Cloud](#deployment)

**Scoring:** Macro 25% · Supply/Demand 35% · Sentiment 20% · Technical 20%

| Factor Group | Signals |
|---|---|
| **Macro** | DXY, Real Yield, Fed Funds, CPI YoY, PCE, Yield Curve |
| **Supply/Demand** | EIA Crude/Gasoline/Distillate draws, Crude Imports YoY, Baker Hughes Rig Count, Seasonal Demand Model, Brent-WTI Spread |
| **Sentiment** | CFTC COT (WTI #067651), XLE/XOP/USO ETF flows |
| **Technical** | 20/50/200W MA, RSI(14), MACD, OVX (Oil Volatility Index) |
| **ICT Analysis** | Daily swing structure, Order Blocks, Fair Value Gaps, Fibonacci OTE |

**API Keys needed (both free):**
- `FRED_API_KEY` — [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) — macro data + rig count
- `EIA_API_KEY` — [eia.gov/opendata](https://www.eia.gov/opendata/register.php) — weekly inventory draws

---

### 🥇 Gold Dashboard — XAU/USD Bias
`gold_dashboard/` · [Deploy on Streamlit Cloud](#deployment)

**Scoring:** Macro 35% · Sentiment 30% · Technical 25% · Cross-Asset 10%

| Factor Group | Signals |
|---|---|
| **Macro** | DXY, Real Yield, Breakeven Inflation, Fed Funds, CPI, PCE, Yield Curve |
| **Sentiment** | CFTC COT (Gold #088691), GLD/IAU/GDXJ ETF flows |
| **Technical** | 20/50/200W MA, RSI(14), MACD, Bollinger Bands |
| **Cross-Asset** | SPX, VIX, TLT, USD/JPY, Silver |
| **ICT Analysis** | Monthly/Weekly/Daily structure, OBs, FVGs, OTE |

**API Key needed:**
- `FRED_API_KEY` — macro data

---

### ₿ BTC Dashboard — Bitcoin Bias
`btc_dashboard/` · [Deploy on Streamlit Cloud](#deployment)

**Scoring:** Macro 30% · Sentiment 35% · Technical 25% · Cross-Asset 10%

| Factor Group | Signals |
|---|---|
| **Macro** | DXY, Real Yield, Fed Funds, CPI, Yield Curve, Halving Cycle Phase |
| **Sentiment** | Fear & Greed Index, CME COT (BTC #133741), Spot ETF flows (IBIT/FBTC/GBTC/ARKB/HODL/BITB), Funding Rate, Open Interest |
| **Technical** | 20/50/200W MA, RSI(14), MACD, Bollinger Bands |
| **Cross-Asset** | SPX, QQQ, VIX, Gold, DXY |
| **On-Chain** | Hash Rate, Miner Revenue, BTC Dominance |
| **ICT Analysis** | Daily structure, OBs, FVGs, OTE |

**API Key needed:**
- `FRED_API_KEY` — macro data
- All other data (Fear & Greed, on-chain, ETF flows, derivatives) are free with no key required

---

## Architecture

Each dashboard follows the same 7-file pattern:

```
dashboard/
├── config.py          # All constants — tickers, weights, thresholds
├── data_fetcher.py    # API calls — yfinance, FRED, CFTC, EIA
├── indicators.py      # Technical calculations (MA, RSI, MACD, etc.)
├── scoring.py         # Weighted bias score [-1.0, +1.0]
├── charts.py          # Plotly figure builders
├── ict_analysis.py    # ICT engine (swing, OB, FVG, OTE, Fibonacci)
└── app.py             # Streamlit entry point
```

**Data sources (all free):**
- Yahoo Finance — price data, ETFs, futures (no key)
- FRED REST API — macro data, rig count (free key)
- CFTC — COT disaggregated futures reports (no key)
- EIA Open Data API v2 — petroleum inventories (free key, oil only)
- Alternative.me — Fear & Greed Index (no key, BTC only)
- Binance — funding rate, open interest (no key, BTC only)
- Blockchain.com — hash rate, miner revenue (no key, BTC only)
- CoinGecko — BTC dominance (no key, BTC only)

---

## Deployment

### Local

```bash
cd oil_dashboard      # or gold_dashboard / btc_dashboard
pip install -r requirements.txt
cp .env.example .env
# Edit .env and fill in your API keys
streamlit run app.py
```

### Streamlit Cloud (free hosting)

1. Fork or clone this repo to your GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, branch `master`, and set the main file:
   - Oil: `oil_dashboard/app.py`
   - Gold: `gold_dashboard/app.py`
   - BTC: `btc_dashboard/app.py`
4. Under **Advanced settings → Secrets**, add:
   ```toml
   FRED_API_KEY = "your_fred_key"
   EIA_API_KEY  = "your_eia_key"   # oil dashboard only
   ```
5. Click **Deploy**

---

## Disclaimer

These dashboards are for **informational and educational purposes only**. Nothing here constitutes financial advice. Always do your own research before making trading or investment decisions.
