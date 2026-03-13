# =============================================================================
# Trade Ideas Dashboard — Data Fetcher
# =============================================================================
"""
Fetches all market data needed by the trade ideas engine:
  - Weekly OHLCV (Weinstein stage, 2 years)
  - Daily OHLCV (PDH/PDL daily bias, 1 year)
  - 4H OHLCV (ICT engine, 60 days)
  - CFTC COT disaggregated report (commercial hedger data)

All fetch functions return empty DataFrames on failure — never raise to caller.
"""
import io
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_ago(days: int) -> str:
    return (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")


def _years_ago(years: int) -> str:
    return _date_ago(365 * years)


def _flatten(raw: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance and strip timezone."""
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker:
            try:
                raw = raw[ticker]
            except KeyError:
                raw.columns = raw.columns.get_level_values(0)
        else:
            raw.columns = raw.columns.get_level_values(0)
    needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[needed].dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


_EMPTY = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


# ---------------------------------------------------------------------------
# Weekly OHLCV — all assets (for Weinstein stage)
# ---------------------------------------------------------------------------

def fetch_weekly_data(years: int = config.WEEKLY_HISTORY_YEARS) -> dict[str, pd.DataFrame]:
    """
    Download weekly OHLCV for all assets in config.ASSETS.
    Returns {asset_key: DataFrame(Open,High,Low,Close,Volume)}.
    """
    start = _years_ago(years)
    tickers = {k: v["ticker"] for k, v in config.ASSETS.items()}
    result = {}

    for key, ticker in tickers.items():
        try:
            raw = yf.download(
                ticker,
                start=start,
                interval="1wk",
                auto_adjust=True,
                progress=False,
            )
            result[key] = _flatten(raw)
        except Exception:
            result[key] = _EMPTY.copy()

    return result


# ---------------------------------------------------------------------------
# Daily OHLCV — all assets (for PDH/PDL daily bias)
# ---------------------------------------------------------------------------

def fetch_daily_data(days: int = config.DAILY_HISTORY_DAYS) -> dict[str, pd.DataFrame]:
    """
    Download daily OHLCV for all assets.
    Returns {asset_key: DataFrame(Open,High,Low,Close,Volume)}.
    """
    start = _date_ago(days)
    result = {}

    for key, asset in config.ASSETS.items():
        try:
            raw = yf.download(
                asset["ticker"],
                start=start,
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
            result[key] = _flatten(raw)
        except Exception:
            result[key] = _EMPTY.copy()

    return result


# ---------------------------------------------------------------------------
# 4H OHLCV — all assets (for ICT engine)
# ---------------------------------------------------------------------------

def fetch_4h_data(days: int = config.INTRADAY_4H_DAYS) -> dict[str, pd.DataFrame]:
    """
    Download 4-hour OHLCV for all assets.
    Returns {asset_key: DataFrame(Open,High,Low,Close,Volume)}.
    Note: yfinance 4h only available for ~60 days back.
    """
    start = _date_ago(days)
    result = {}

    for key, asset in config.ASSETS.items():
        try:
            raw = yf.download(
                asset["ticker"],
                start=start,
                interval="4h",
                auto_adjust=True,
                progress=False,
            )
            result[key] = _flatten(raw)
        except Exception:
            result[key] = _EMPTY.copy()

    return result


# ---------------------------------------------------------------------------
# CFTC COT — disaggregated futures report
# ---------------------------------------------------------------------------

def _download_cot_year(year: int) -> pd.DataFrame | None:
    """Download and unzip a single year of CFTC disaggregated futures COT report."""
    url = config.COT_REPORT_URL_TEMPLATE.format(year=year)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            fname = z.namelist()[0]
            with z.open(fname) as f:
                return pd.read_csv(f, low_memory=False)
    except Exception:
        return None


def _extract_cot_for_code(frames: list[pd.DataFrame], cot_code: str) -> pd.DataFrame:
    """
    Filter combined COT frames to a specific contract code and return weekly
    DataFrame with commercial net positions (comm_long, comm_short, comm_net).
    """
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Find contract code column
    code_col = None
    for col in combined.columns:
        if "contract" in col.lower() and "code" in col.lower():
            code_col = col
            break
    if code_col is None:
        return pd.DataFrame()

    filtered = combined[combined[code_col].astype(str).str.strip() == cot_code].copy()
    if filtered.empty:
        return pd.DataFrame()

    # Find date column
    date_col = None
    for c in ["Report_Date_as_YYYY-MM-DD", "As_of_Date_In_Form_YYMMDD", "Report_Date_as_MM_DD_YYYY"]:
        if c in filtered.columns:
            date_col = c
            break
    if date_col is None:
        return pd.DataFrame()

    filtered["date"] = pd.to_datetime(filtered[date_col], errors="coerce")
    filtered = filtered.dropna(subset=["date"]).sort_values("date")

    # Column mapping — disaggregated report
    col_map = {
        "Prod_Merc_Positions_Long_All":  "comm_long",
        "Prod_Merc_Positions_Short_All": "comm_short",
        "M_Money_Positions_Long_All":    "noncomm_long",
        "M_Money_Positions_Short_All":   "noncomm_short",
        "Open_Interest_All":             "open_interest",
    }

    keep_cols = ["date"] + [c for c in col_map if c in filtered.columns]
    out = filtered[keep_cols].copy().rename(columns=col_map)
    out = out.drop_duplicates(subset=["date"]).set_index("date")

    if "comm_long" in out.columns and "comm_short" in out.columns:
        out["comm_net"] = out["comm_long"] - out["comm_short"]
    if "noncomm_long" in out.columns and "noncomm_short" in out.columns:
        out["noncomm_net"] = out["noncomm_long"] - out["noncomm_short"]

    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


def fetch_cot_data(years: int = config.COT_HISTORICAL_YEARS) -> dict[str, pd.DataFrame]:
    """
    Download CFTC COT data for all assets that have a COT code.
    Returns {asset_key: DataFrame(comm_long, comm_short, comm_net, noncomm_net)}.
    Assets without a COT code (e.g. BTC) get an empty DataFrame.
    """
    current_year = datetime.today().year
    year_range = range(current_year - years + 1, current_year + 1)

    # Download raw CSVs once (reuse across assets)
    raw_frames: list[pd.DataFrame] = []
    for y in year_range:
        df = _download_cot_year(y)
        if df is not None:
            raw_frames.append(df)

    result = {}
    for key, asset in config.ASSETS.items():
        cot_code = asset.get("cot_code")
        if not cot_code:
            result[key] = pd.DataFrame()
        else:
            result[key] = _extract_cot_for_code(raw_frames, cot_code)

    return result


# ---------------------------------------------------------------------------
# Master fetch — single call that returns everything
# ---------------------------------------------------------------------------

def fetch_all_data() -> dict:
    """
    Fetch all data needed by the dashboard in one call.
    Returns:
    {
        "weekly":     {asset_key: DataFrame},
        "daily":      {asset_key: DataFrame},
        "4h":         {asset_key: DataFrame},
        "cot":        {asset_key: DataFrame},
        "fetched_at": datetime,
    }
    """
    return {
        "weekly":     fetch_weekly_data(),
        "daily":      fetch_daily_data(),
        "4h":         fetch_4h_data(),
        "cot":        fetch_cot_data(),
        "fetched_at": datetime.now(),
    }
