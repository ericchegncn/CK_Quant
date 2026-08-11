#!/usr/bin/env python
"""确认白名单对数和 number_assets 配置"""
import os, sys
import paramiko

HOST = os.environ["CK_QUANT_SSH_HOST"]
USER = os.getenv("CK_QUANT_SSH_USER", "root")
PASSWORD = os.environ["CK_QUANT_SSH_PASSWORD"]
cmd = r"""
echo '=== config 中的 number_assets ==='
grep -n "number_assets" /root/ft_userdata/user_data/config_HC.json
echo '=== 容器日志中的白名单 ==='
docker logs CK_Quant --tail 200 2>&1 | grep -E "Whitelist with" | tail -1
echo '=== 当前持仓数 ==='
docker logs CK_Quant --tail 50 2>&1 | grep -E "Found open trade|open orders" | tail -3
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
