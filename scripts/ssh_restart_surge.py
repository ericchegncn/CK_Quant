#!/usr/bin/env python
"""重启 CK_Quant 容器应用 CK_Trend_Surge"""
import os, sys
import paramiko

HOST = os.environ["CK_QUANT_SSH_HOST"]
USER = os.getenv("CK_QUANT_SSH_USER", "root")
PASSWORD = os.environ["CK_QUANT_SSH_PASSWORD"]
cmd = r"""
set -e
cd /root/ft_userdata
echo '=== 停止旧容器 ==='
docker compose down 2>&1 | tail -3 || docker stop CK_Quant 2>&1 | tail -1
sleep 3
echo '=== 启动新容器 ==='
docker compose up -d 2>&1 | tail -5
sleep 15
echo '=== 容器状态 ==='
docker ps --format '{{.Names}} | {{.Status}}' | grep CK_Quant
echo '=== 启动日志（策略部分） ==='
docker logs CK_Quant --tail 40 2>&1 | grep -iE "strategy|using|error|exception|fatal" | head -15
echo '=== 完整启动日志尾部 ==='
docker logs CK_Quant --tail 15 2>&1
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
