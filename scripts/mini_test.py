import sys, time, datetime as dt
import ccxt
print("step1: imports ok", flush=True)
ex = ccxt.binance({"options": {"defaultType": "swap"}})
print("step2: ccxt init ok", flush=True)
start_ms = int(dt.datetime(2025,9,16,0,0,tzinfo=dt.timezone.utc).timestamp()*1000)
batch = ex.fetch_trades('BTC/USDT:USDT', since=start_ms, limit=5)
print(f"step3: fetched {len(batch)}", flush=True)
