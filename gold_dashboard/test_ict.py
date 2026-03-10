import sys
sys.path.insert(0, r'D:\Trading_Investing\gold_dashboard')
import data_fetcher
import ict_analysis

print('Fetching real data...')
mdf = data_fetcher.fetch_monthly_prices()
wdf = data_fetcher.fetch_weekly_gold_ohlcv()
ddf = data_fetcher.fetch_daily_prices()

print('Monthly rows:', len(mdf), 'Weekly rows:', len(wdf), 'Daily rows:', len(ddf))
if not ddf.empty:
    print('Current gold close:', round(float(ddf['Close'].iloc[-1]), 1))

kl = ict_analysis.get_key_levels(mdf, wdf)
print('PWH:', kl.get('PWH'), 'PWL:', kl.get('PWL'), 'PMH:', kl.get('PMH'), 'PML:', kl.get('PML'))

sh, sl, direction = ict_analysis._find_major_swing(wdf)
fib = ict_analysis.calc_fibonacci_levels(sh, sl)
print('Swing high:', round(sh,1), 'Swing low:', round(sl,1), 'Direction:', direction)
if fib:
    print('50% fib:', fib.get(0.5), 'OTE:', fib.get(0.618), '-', fib.get(0.705))

ms_m = ict_analysis.detect_market_structure(mdf)
ms_w = ict_analysis.detect_market_structure(wdf)
print('Monthly structure:', ms_m)
print('Weekly structure:', ms_w)

trades = ict_analysis.generate_ict_trades(mdf, wdf, ddf, bias_score=0.40)
print()
for t in trades:
    print('Trade', t['id'], ':', t['direction'], '|', t['setup_name'])
    print('  Confidence:', t['confidence'], '| Entry:', t['entry'], '| Stop:', t['stop'], '| TP1:', t['target1'])
    print('  Rationale:', str(t['rationale'])[:120])
    print()
