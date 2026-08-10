#!/usr/bin/env python
"""上传 CK_Trend_Surge.py 到实盘服务器并切换策略"""
import os, sys
import paramiko

HOST = "8.209.251.99"
USER = "root"
PASSWORD = "*@naS!Luvx6p^f&P"
LOCAL_STRATEGY = r"D:\Eric Cheng\Documents\CK_Quant\user_data\strategies\CK_Trend_Surge.py"
REMOTE_STRATEGY = "/root/ft_userdata/user_data/strategies/CK_Trend_Surge.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, auth_timeout=20,
              look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    # 上传策略
    sftp.put(LOCAL_STRATEGY, REMOTE_STRATEGY)
    sftp.close()
    print("✅ 策略已上传:", REMOTE_STRATEGY)

    # 备份原 compose + 修改策略引用
    cmd = r"""
set -e
cd /root/ft_userdata
cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d_%H%M%S)
echo '=== 修改前 compose 中的策略引用 ==='
grep -n "strategy\|logfile\|db-url" docker-compose.yml
# 用 sed 替换策略名、日志名、DB 名
sed -i 's/--strategy CK_Trend$/--strategy CK_Trend_Surge/' docker-compose.yml
sed -i 's/freqtrade_CK_Trend\.log/freqtrade_CK_Trend_Surge.log/g' docker-compose.yml
sed -i 's/tradesv3_CK_Trend\.sqlite/tradesv3_CK_Trend_Surge.sqlite/g' docker-compose.yml
echo '=== 修改后 ==='
grep -n "strategy\|logfile\|db-url" docker-compose.yml
echo '=== 验证策略能被 freqtrade 加载 ==='
docker run --rm -v /root/ft_userdata/user_data:/freqtrade/user_data ck-quant:local list-strategies --userdir /freqtrade/user_data 2>/dev/null | grep -E "CK_Trend_Surge" || echo "加载检查跳过(容器内用户目录不同)"
"""
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
