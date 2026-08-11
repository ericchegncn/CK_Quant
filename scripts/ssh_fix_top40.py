#!/usr/bin/env python
"""清理残留 WAL + 改 top30→top40 + 验证订单可见性"""
import os, sys
import paramiko

HOST = os.environ["CK_QUANT_SSH_HOST"]
USER = os.getenv("CK_QUANT_SSH_USER", "root")
PASSWORD = os.environ["CK_QUANT_SSH_PASSWORD"]
cmd = r"""
set -e
cd /root/ft_userdata
echo '=== 1. 清理残留 Surge WAL/SHM 文件 ==='
rm -f user_data/tradesv3_CK_Trend_Surge.sqlite-shm user_data/tradesv3_CK_Trend_Surge.sqlite-wal
ls -la user_data/*.sqlite* 2>/dev/null

echo ''
echo '=== 2. 修改 config_HC.json: number_assets 30 → 40 ==='
cp user_data/config_HC.json user_data/config_HC.json.bak.$(date +%Y%m%d_%H%M%S)
sed -i 's/"number_assets": 30/"number_assets": 40/' user_data/config_HC.json
grep -n "number_assets" user_data/config_HC.json

echo ''
echo '=== 3. 重启容器 ==='
docker compose down 2>&1 | tail -2
sleep 3
docker compose up -d 2>&1 | tail -3
sleep 15

echo ''
echo '=== 4. 容器状态 ==='
docker ps --format '{{.Names}} | {{.Status}}' | grep CK_Quant

echo ''
echo '=== 5. 确认白名单 40 对 ==='
docker logs CK_Quant --tail 60 2>&1 | grep -E "Whitelist with" | tail -1

echo ''
echo '=== 6. 确认 DB 订单仍可读 ==='
docker exec CK_Quant python3 -c "
import sqlite3
c = sqlite3.connect('/freqtrade/user_data/tradesv3_CK_Trend.sqlite')
n = c.execute('SELECT COUNT(*) FROM trades').fetchone()[0]
o = c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
print(f'trades={n} orders={o}')
# 显示最近 5 笔
for r in c.execute('SELECT pair, is_open, open_date, close_date FROM trades ORDER BY open_date DESC LIMIT 5'):
    print(r)
c.close()
" 2>&1 | tail -8

echo ''
echo '=== 7. 容器日志确认无错误 ==='
docker logs CK_Quant --tail 30 2>&1 | grep -iE "error|fatal|exception" | head -5 || echo "无错误"
docker logs CK_Quant --tail 5 2>&1
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, auth_timeout=20,
              look_for_keys=False, allow_agent=False)
    _, o, e = c.exec_command(cmd, timeout=150)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
