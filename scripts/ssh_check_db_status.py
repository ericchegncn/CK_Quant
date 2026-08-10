#!/usr/bin/env python
"""检查实盘 DB 实际使用情况和配置"""
import os, sys
import paramiko

HOST = "8.209.251.99"
USER = "root"
PASSWORD = "*@naS!Luvx6p^f&P"

cmd = r"""
set -e
cd /root/ft_userdata
echo '=== config_HC.json 中 db/strategy/pairlist 相关 ==='
grep -nE "db_url|db-url|strategy|VolumePairList|number_assets|max_open_trades" user_data/config_HC.json 2>/dev/null | head -15
echo ''
echo '=== 容器实际运行的命令 ==='
docker inspect CK_Quant --format '{{.Config.Cmd}}' 2>/dev/null
echo ''
echo '=== DB 文件列表 ==='
ls -la user_data/*.sqlite* 2>/dev/null
echo ''
echo '=== 各 DB 的 trades 数量 ==='
for db in user_data/*.sqlite; do
  echo "--- $db"
  docker exec CK_Quant python3 -c "
import sqlite3, os
db = '$db'
if os.path.exists(db):
    c = sqlite3.connect(db)
    try:
        n = c.execute('SELECT COUNT(*) FROM trades').fetchone()[0]
        o = c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        print(f'trades={n} orders={o}')
    except Exception as e:
        print('ERR:', e)
    c.close()
" 2>&1 | tail -1
done
echo ''
echo '=== 容器日志中的 DB 错误 ==='
docker logs CK_Quant --tail 100 2>&1 | grep -iE "sqlite|database|db-url|error.*db|lock" | head -10
echo ''
echo '=== Telegram 状态消息 ==='
docker logs CK_Quant --tail 50 2>&1 | grep -iE "status|trade|open" | tail -8
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, auth_timeout=20,
              look_for_keys=False, allow_agent=False)
    _, o, e = c.exec_command(cmd, timeout=90)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
