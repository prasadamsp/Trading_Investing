# =============================================================================
# Bitcoin Weekly Bias Dashboard — Data Fetcher
# =============================================================================
import io
import os
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

import config

load_dotenv()


def _get_fred_key() -> str:
    """Read FRED API key from .env (local) or Streamlit secrets (cloud)."""
    key = os.getenv("FRED_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets["FRED_API_KEY"]
        except (KeyError, FileNotFoundError, Exception):
            pass
    return key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _years_ago(n: int) -> str:
    return (datetime.today() - timedelta(days=365 * n)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------

def fetch_weekly_prices(years: int = config.PRICE_HISTORY_YEARS) -> dict[str, pd.DataFrame]:
    """
    Download weekly OHLCV for every ticker in config.TICKERS.
    Returns dict {key: DataFrame with weekly Close}.
    """
    start = _years_ago(years)
    result = {}
    tickers_list = list(config.TICKERS.values())
    keys_list = list(config.TICKERS.keys())

    raw = yf.download(
        tickers_list,
        start=start,
        interval="1wk",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )

    for key, ticker in zip(keys_list, tickers_list):
        try:
            if len(tickers_list) == 1:
                df = raw[["Close"]].dropna()
            else:
                df = raw[ticker][["Close"]].dropna()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            result[key] = df
        except Exception:
            result[key] = pd.DataFrame(columns=["Close"])

    return result


def fetch_etf_shares_outstanding() -> dict[str, float | None]:
    """
    Return current shares outstanding for each BTC ETF.
    Used to track week-over-week flow.
    """
    etf_keys = ["ibit", "fbtc", "gbtc", "arkb", "hodl", "bitb"]
    result = {}
    for key in etf_keys:
        ticker = config.TICKERS[key]
        try:
            info = yf.Ticker(ticker).info
            shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            result[key] = shares
        except Exception:
            result[key] = None
    return result


# ---------------------------------------------------------------------------
# FRED API
# ---------------------------------------------------------------------------

def fetch_fred_series(years: int = config.PRICE_HISTORY_YEARS, api_key: str = "") -> dict[str, pd.Series]:
    """
    Download FRED series via direct REST API (no fredapi library needed).
    Falls back gracefully if FRED_API_KEY is missing.
    """
    api_key = api_key or _get_fred_key()
    result = {}

    if not api_key:
        for k in config.FRED_SERIES:
            result[k] = pd.Series(dtype=float, name=k)
        return result

    start = _years_ago(years)
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    for key, series_id in config.FRED_SERIES.items():
        try:
            resp = requests.get(base_url, params={
                "series_id":         series_id,
                "api_key":           api_key,
                "file_type":         "json",
                "observation_start": start,
            }, timeout=15)
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            dates  = [o["date"] for o in obs]
            values = [float(o["value"]) if o["value"] != "." else float("nan") for o in obs]
            s = pd.Series(values, index=pd.to_datetime(dates), name=key).dropna()
            result[key] = s
        except Exception:
            result[key] = pd.Series(dtype=float, name=key)

    return result


# ---------------------------------------------------------------------------
# CFTC COT Report — Bitcoin Futures (CME)
# ---------------------------------------------------------------------------

def _cot_url(year: int) -> str:
    return config.COT_REPORT_URL_TEMPLATE.format(year=year)


def _download_cot_year(year: int) -> pd.DataFrame | None:
    url = _cot_url(year)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            fname = z.namelist()[0]
            with z.open(fname) as f:
                df = pd.read_csv(f, low_memory=False)
        return df
    except Exception:
        return None


def fetch_cot_btc(years: int = config.COT_HISTORICAL_YEARS) -> pd.DataFrame:
    """
    Download CFTC disaggregated COT report for BTC futures (CME).
    Returns weekly DataFrame with:
        date, noncomm_long, noncomm_short, noncomm_net, comm_long, comm_short, comm_net
    """
    current_year = datetime.today().year
    frames = []

    for y in range(current_year - years + 1, current_year + 1):
        df = _download_cot_year(y)
        if df is None:
            continue
        btc = df[df["CFTC_Contract_Market_Code"].astype(str).str.strip() == config.COT_BTC_CODE].copy()
        if btc.empty:
            for col in df.columns:
                if "contract" in col.lower() and "code" in col.lower():
                    btc = df[df[col].astype(str).str.strip() == config.COT_BTC_CODE].copy()
                    break
        if btc.empty:
            continue
        frames.append(btc)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    date_col = None
    for c in ["Report_Date_as_YYYY-MM-DD", "As_of_Date_In_Form_YYMMDD", "Report_Date_as_MM_DD_YYYY"]:
        if c in combined.columns:
            date_col = c
            break
    if date_col is None:
        return pd.DataFrame()

    combined["date"] = pd.to_datetime(combined[date_col], errors="coerce")
    combined = combined.dropna(subset=["date"]).sort_values("date")

    col_map = {
        "M_Money_Positions_Long_All":  "noncomm_long",
        "M_Money_Positions_Short_All": "noncomm_short",
        "Prod_Merc_Positions_Long_All":  "comm_long",
        "Prod_Merc_Positions_Short_All": "comm_short",
        "Open_Interest_All":             "open_interest",
    }

    out = combined[["date"] + [c for c in col_map if c in combined.columns]].copy()
    out = out.rename(columns=col_map)
    out = out.drop_duplicates(subset=["date"]).set_index("date")

    if "noncomm_long" in out.columns and "noncomm_short" in out.columns:
        out["noncomm_net"] = out["noncomm_long"] - out["noncomm_short"]
    if "comm_long" in out.columns and "comm_short" in out.columns:
        out["comm_net"] = out["comm_long"] - out["comm_short"]

    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


# ---------------------------------------------------------------------------
# Crypto Fear & Greed Index (alternative.me — no API key required)
# ---------------------------------------------------------------------------

def fetch_fear_greed() -> pd.DataFrame:
    """
    Fetch Crypto Fear & Greed Index from alternative.me.
    Returns DataFrame with columns: value (0-100), classification.
    Index = date (daily).
    """
    try:
        resp = requests.get(config.FEAR_GREED_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return pd.DataFrame(columns=["value", "classification"])

        rows = []
        for item in data:
            try:
                date = pd.to_datetime(int(item["timestamp"]), unit="s").normalize()
                rows.append({
                    "date":           date,
                    "value":          int(item["value"]),
                    "classification": item.get("value_classification", ""),
                })
            except Exception:
                continue

        df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
        df = df.set_index("date")
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame(columns=["value", "classification"])


# ---------------------------------------------------------------------------
# ICT-specific fetchers (daily, weekly OHLCV, monthly for BTC)
# ---------------------------------------------------------------------------

def _flatten_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance single-ticker downloads."""
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[needed].dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def fetch_weekly_btc_ohlcv(years: int = config.PRICE_HISTORY_YEARS) -> pd.DataFrame:
    """Full OHLCV for BTC-USD at weekly resolution."""
    start = _years_ago(years)
    try:
        raw = yf.download(
            "BTC-USD",
            start=start,
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )
        return _flatten_ohlcv(raw)
    except Exception:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


def fetch_monthly_prices(years: int = config.ICT_MONTHLY_YEARS) -> pd.DataFrame:
    """Monthly OHLCV for BTC-USD over the last `years` years (for ICT structure)."""
    start = _years_ago(years)
    try:
        raw = yf.download(
            "BTC-USD",
            start=start,
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )
        return _flatten_ohlcv(raw)
    except Exception:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


def fetch_daily_prices(days: int = config.ICT_DAILY_DAYS) -> pd.DataFrame:
    """Daily OHLCV for BTC-USD over the last `days` calendar days."""
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        raw = yf.download(
            "BTC-USD",
            start=start,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        return _flatten_ohlcv(raw)
    except Exception:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


# ---------------------------------------------------------------------------
# On-Chain Metrics — blockchain.com Charts API (no API key required)
# ---------------------------------------------------------------------------

def fetch_onchain_metrics() -> dict[str, pd.Series]:
    """
    Fetch BTC on-chain metrics from blockchain.com charts API.
    Returns dict of {metric_name: pd.Series (index=date, values=metric)}.
    No API key required.
    """
    chart_map = {
        "hash_rate":      "hash-rate",
        "miner_revenue":  "miners-revenue",
    }
    result: dict[str, pd.Series] = {}

    for key, chart_name in chart_map.items():
        url = (
            f"{config.BLOCKCHAIN_API_BASE}/{chart_name}"
            f"?timespan={config.BLOCKCHAIN_TIMESPAN}&format=json&sampled=true"
        )
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            values = resp.json().get("values", [])
            if not values:
                result[key] = pd.Series(dtype=float, name=key)
                continue
            df = pd.DataFrame(values)
            df["date"] = pd.to_datetime(df["x"], unit="s").dt.normalize()
            s = df.set_index("date")["y"].rename(key)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            result[key] = s.dropna()
        except Exception:
            result[key] = pd.Series(dtype=float, name=key)

    return result


# ---------------------------------------------------------------------------
# BTC Market Dominance — CoinGecko free API (no key required)
# ---------------------------------------------------------------------------

def fetch_btc_dominance() -> float | None:
    """
    Fetch current BTC market dominance % from CoinGecko global endpoint.
    Returns float (e.g. 54.3) or None on failure.
    """
    try:
        resp = requests.get(config.COINGECKO_GLOBAL_URL, timeout=10)
        resp.raise_for_status()
        dominance = resp.json().get("data", {}).get("market_cap_percentage", {}).get("btc")
        return round(float(dominance), 2) if dominance else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# OKX public API — Funding Rate (no API key, globally accessible)
# ---------------------------------------------------------------------------

def fetch_funding_rate() -> pd.DataFrame:
    """
    Fetch BTC/USDT perpetual funding rate history from OKX v5 public API.
    Returns DataFrame with column: rate (% per 8h), indexed by timestamp.
    No API key required.
    """
    try:
        resp = requests.get(
            config.OKX_FUNDING_URL,
            params={
                "instId": config.OKX_INSTRUMENT,
                "limit":  config.OKX_FUNDING_LIMIT,
            },
            timeout=10,
        )
        resp.raise_for_status()
        records = resp.json().get("data", [])
        if not records:
            return pd.DataFrame(columns=["rate"])
        rows = [
            {
                "timestamp": pd.to_datetime(int(r["fundingTime"]), unit="ms"),
                "rate":      float(r["fundingRate"]) * 100,   # convert to %
            }
            for r in records
        ]
        df = pd.DataFrame(rows).sort_values("timestamp").set_index("timestamp")
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame(columns=["rate"])


# ---------------------------------------------------------------------------
# OKX public API — Open Interest History (no API key, globally accessible)
# ---------------------------------------------------------------------------

def fetch_open_interest_hist() -> pd.DataFrame:
    """
    Fetch BTC perpetual open interest history from OKX v5 (30 daily bars).
    Returns DataFrame with column: oi_usd (USD value), indexed by date.
    No API key required.
    """
    try:
        resp = requests.get(
            config.OKX_OI_URL,
            params={
                "ccy":    "BTC",
                "period": config.OKX_OI_PERIOD,
            },
            timeout=10,
        )
        resp.raise_for_status()
        records = resp.json().get("data", [])
        if not records:
            return pd.DataFrame(columns=["oi_usd"])
        rows = [
            {
                "timestamp": pd.to_datetime(int(r[0]), unit="ms").normalize(),
                "oi_usd":    float(r[1]),
            }
            for r in records
        ]
        df = pd.DataFrame(rows).sort_values("timestamp").set_index("timestamp")
        df = df.tail(config.OKX_OI_LIMIT)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame(columns=["oi_usd"])


# ---------------------------------------------------------------------------
# Aggregate fetch — single call that returns everything
# ---------------------------------------------------------------------------

def fetch_all_data(fred_key: str = "") -> dict:
    """
    Master fetcher. Returns:
    {
        "prices":       dict of weekly Close DataFrames keyed by config name,
        "etf_shares":   dict of current BTC ETF shares outstanding,
        "fred":         dict of FRED Series,
        "cot":          DataFrame of weekly BTC CME COT data,
        "fear_greed":   DataFrame of daily Fear & Greed index,
        "weekly_btc":   pd.DataFrame OHLCV at weekly interval (for ICT),
        "monthly_btc":  pd.DataFrame OHLCV at monthly interval (for ICT),
        "daily_btc":    pd.DataFrame OHLCV at daily interval (for ICT chart),
        "fetched_at":   datetime
    }
    """
    prices        = fetch_weekly_prices()
    etf_shares    = fetch_etf_shares_outstanding()
    fred          = fetch_fred_series(api_key=fred_key)
    cot           = fetch_cot_btc()
    fear_greed    = fetch_fear_greed()
    weekly_btc    = fetch_weekly_btc_ohlcv()
    monthly_btc   = fetch_monthly_prices()
    daily_btc     = fetch_daily_prices()
    onchain       = fetch_onchain_metrics()
    btc_dominance = fetch_btc_dominance()
    funding_rate  = fetch_funding_rate()
    open_interest = fetch_open_interest_hist()

    return {
        "prices":        prices,
        "etf_shares":    etf_shares,
        "fred":          fred,
        "cot":           cot,
        "fear_greed":    fear_greed,
        "weekly_btc":    weekly_btc,
        "monthly_btc":   monthly_btc,
        "daily_btc":     daily_btc,
        "onchain":       onchain,
        "btc_dominance": btc_dominance,
        "funding_rate":  funding_rate,
        "open_interest": open_interest,
        "fetched_at":    datetime.now(),
    }
