import sys
sys.path.insert(0, r'D:\Trading_Investing\gold_dashboard')

import data_fetcher
import ict_analysis

print("Fetching data...")
monthly = data_fetcher.fetch_monthly_prices()
weekly  = data_fetcher.fetch_weekly_gold_ohlcv()
daily   = data_fetcher.fetch_daily_prices()

print(f"Monthly rows: {len(monthly)}, Weekly rows: {len(weekly)}, Daily rows: {len(daily)}")
print(f"Daily columns: {list(daily.columns)}")
if not daily.empty:
    print(f"Current gold price: ${daily['Close'].iloc[-1]:.1f}")
    print(f"Daily date range: {daily.index[0].date()} to {daily.index[-1].date()}")

print("\nRunning generate_ict_trades with bias_score=0.35...")
trades = ict_analysis.generate_ict_trades(monthly, weekly, daily, bias_score=0.35)

for t in trades:
    print(f"\n--- Trade {t['id']} ---")
    print(f"  Direction:  {t['direction']}")
    print(f"  Setup:      {t['setup_name']}")
    print(f"  Entry:      {t['entry']}")
    print(f"  Stop:       {t['stop']}")
    print(f"  TP1:        {t['target1']}  R:R {t['rr1']}")
    print(f"  TP2:        {t['target2']}  R:R {t['rr2']}")
    print(f"  Confidence: {t['confidence']}")
    print(f"  Rationale:  {t['rationale'][:120]}")
