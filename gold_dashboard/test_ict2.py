import sys
sys.path.insert(0, r'D:\Trading_Investing\gold_dashboard')
import data_fetcher
import ict_analysis

print('Fetching real data...')
mdf = data_fetcher.fetch_monthly_prices()
wdf = data_fetcher.fetch_weekly_gold_ohlcv()
ddf = data_fetcher.fetch_daily_prices()

print('Monthly:', len(mdf), 'Weekly:', len(wdf), 'Daily:', len(ddf))
cp = float(ddf['Close'].iloc[-1])
print('Current price:', round(cp, 1))

# Test the fixed swing
sh, sl, d = ict_analysis._find_major_swing(ddf, lookback_bars=30)
if sh - sl < cp * 0.01:
    sh, sl, d = ict_analysis._find_major_swing(ddf, lookback_bars=60)
fib = ict_analysis.calc_fibonacci_levels(sh, sl)
print('Daily swing:', round(sl,1), '->', round(sh,1), '|', d)
if fib:
    print('50% fib:', fib.get(0.5), '| OTE zone:', fib.get(0.705), '-', fib.get(0.618))

kl = ict_analysis.get_key_levels(mdf, wdf)
print('PWH:', kl.get('PWH'), 'PWL:', kl.get('PWL'))

trades = ict_analysis.generate_ict_trades(mdf, wdf, ddf, bias_score=0.40)
print()
for t in trades:
    print('Trade', t['id'], ':', t['direction'], '|', t['setup_name'])
    if t['entry']:
        print('  Entry:', t['entry'], '| Stop:', t['stop'], '| TP1:', t['target1'], '| R:R', t['rr1'])
    print('  Conf:', t['confidence'])
    print('  Rationale:', str(t['rationale'])[:120])
    print()
