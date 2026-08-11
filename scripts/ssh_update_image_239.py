#!/usr/bin/env python
"""更新目标实盘服务器镜像到最新版（含新 UI + 回测修复）

安全要点：
- 只更新镜像，绝不动 --db-url（订单历史保留）
- 容器重建后验证 restart=0 + 策略正常运行 + 持仓恢复
"""
import os, sys, time
import paramiko

HOST = os.environ["CK_QUANT_SSH_HOST"]
USER = os.getenv("CK_QUANT_SSH_USER", "root")
PASSWORD = os.environ["CK_QUANT_SSH_PASSWORD"]
cmd = r"""
set -e
cd /root/CK_Quant || { echo "❌ 项目目录不存在"; exit 1; }

echo "=== 1. 当前镜像 ==="
docker images ericchenghz/ck-quant:latest --format "{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}}"
echo ""

echo "=== 2. 拉取最新镜像 ==="
docker compose pull 2>&1 | tail -3
echo ""

echo "=== 3. 记录当前容器状态（备份） ==="
docker inspect CK_Quant --format "restart_count={{.RestartCount}} started={{.State.StartedAt}}" 2>/dev/null || echo "容器未运行"
echo ""

echo "=== 4. 重建容器（用新镜像） ==="
docker compose up -d --force-recreate 2>&1 | tail -5
echo ""

echo "=== 5. 等待启动 ==="
sleep 25
docker ps --filter "name=CK_Quant" --format "{{.Names}} | {{.Status}} | {{.Image}}"
echo ""

echo "=== 6. 验证日志 ==="
docker logs CK_Quant --tail 60 2>&1 | grep -E "Strategy:|Changing state to|Bot heartbeat|Found open trade|ERROR|Fatal" | tail -12
echo ""

echo "=== 7. 确认 DB 未变 ==="
ls -la /root/CK_Quant/user_data/*.sqlite 2>/dev/null | head -5
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PASSWORD, timeout=25, auth_timeout=25,
              look_for_keys=False, allow_agent=False)
    _, o, e = c.exec_command(cmd, timeout=300)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
finally:
    c.close()
