import sys, time, datetime as dt
import ccxt
ex = ccxt.binance({"options": {"defaultType": "swap"}})
start_ms = int(dt.datetime(2025,9,16,0,0,tzinfo=dt.timezone.utc).timestamp()*1000)
end_ms = start_ms + 3600*1000
since = start_ms
total = 0
t0 = time.time()
while since < end_ms:
    try:
        batch = ex.fetch_trades('BTC/USDT:USDT', since=since, limit=1000)
    except Exception as e:
        print(f"err: {e}", flush=True)
        time.sleep(1)
        continue
    if not batch: break
    total += len(batch)
    last_ts = batch[-1]['timestamp']
    if last_ts <= since: since += 1000
    else: since = last_ts + 1
print(f"done: {total} 条, {time.time()-t0:.0f}s", flush=True)
