#!/usr/bin/env python
"""修复 db-url 指向原 DB，保留订单历史后重启"""
import os, sys
import paramiko

HOST = "8.209.251.99"
USER = "root"
PASSWORD = "*@naS!Luvx6p^f&P"

cmd = r"""
set -e
cd /root/ft_userdata
echo '=== 修改前 ==='
grep -n "db-url\|strategy" docker-compose.yml
# 改回原 DB（保留订单历史）；删除新空库
sed -i 's|tradesv3_CK_Trend_Surge\.sqlite|tradesv3_CK_Trend.sqlite|g' docker-compose.yml
rm -f user_data/tradesv3_CK_Trend_Surge.sqlite
echo '=== 修改后 ==='
grep -n "db-url\|strategy" docker-compose.yml
echo '=== 重启容器 ==='
docker compose down 2>&1 | tail -2
sleep 3
docker compose up -d 2>&1 | tail -3
sleep 15
echo '=== 容器状态 ==='
docker ps --format '{{.Names}} | {{.Status}}' | grep CK_Quant
echo '=== 确认 DB 中的订单 ==='
docker exec CK_Quant python3 -c "
import sqlite3
c = sqlite3.connect('/freqtrade/user_data/tradesv3_CK_Trend.sqlite')
for t in ['trades', 'orders']:
    try:
        n = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'{t}: {n} 行')
    except Exception as ex:
        print(f'{t}: {ex}')
c.close()
" 2>&1 | tail -5
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, auth_timeout=20,
              look_for_keys=False, allow_agent=False)
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
