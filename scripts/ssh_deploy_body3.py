#!/usr/bin/env python
"""部署 CK_Trend_Surge_Body3 到实盘（保留原 DB，只改策略名）"""
import os, sys
import paramiko

HOST = os.environ["CK_QUANT_SSH_HOST"]
USER = os.getenv("CK_QUANT_SSH_USER", "root")
PASSWORD = os.environ["CK_QUANT_SSH_PASSWORD"]
LOCAL = r"D:\Eric Cheng\Documents\CK_Quant\user_data\strategies\CK_Trend_Surge_Body3.py"
REMOTE = "/root/ft_userdata/user_data/strategies/CK_Trend_Surge_Body3.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, auth_timeout=20,
              look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    sftp.put(LOCAL, REMOTE)
    sftp.close()
    print("✅ 策略已上传")

    cmd = r"""
set -e
cd /root/ft_userdata
cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d_%H%M%S)
echo '=== 修改前 ==='
grep -n "strategy\|db-url" docker-compose.yml
# 只改策略名，db-url 保持不变（保留订单历史）
sed -i 's/--strategy CK_Trend_Surge_NoVol$/--strategy CK_Trend_Surge_Body3/' docker-compose.yml
echo '=== 修改后 ==='
grep -n "strategy\|db-url" docker-compose.yml
echo '=== 重启 ==='
docker compose down 2>&1 | tail -1
sleep 3
docker compose up -d 2>&1 | tail -2
sleep 15
echo '=== 状态 ==='
docker ps --format '{{.Names}} | {{.Status}}' | grep CK_Quant
echo '=== 日志确认 ==='
docker logs CK_Quant --tail 80 2>&1 | grep -iE "Strategy:|Found open trade|error|fatal" | head -8
"""
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
