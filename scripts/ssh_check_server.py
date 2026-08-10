#!/usr/bin/env python
"""查看服务器配置和容器挂载"""
import os, sys
import paramiko

HOST = "8.209.251.99"
USER = "root"
PASSWORD = "*@naS!Luvx6p^f&P"

cmd = r"""
set -e
echo '=== docker-compose.yml ==='
cat /root/ft_userdata/docker-compose.yml
echo '=== 策略引用配置 ==='
grep -rn "strategy" /root/ft_userdata/user_data/*.json 2>/dev/null | head -10
echo '=== 容器挂载 ==='
docker inspect CK_Quant --format '{{json .Mounts}}' 2>/dev/null | python3 -m json.tool 2>/dev/null | head -30
echo '=== 容器命令 ==='
docker inspect CK_Quant --format '{{.Config.Cmd}} {{.Config.Entrypoint}}' 2>/dev/null
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, auth_timeout=20,
              look_for_keys=False, allow_agent=False)
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
