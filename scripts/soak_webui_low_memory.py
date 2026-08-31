#!/usr/bin/env python3
"""
Soak test for CK_Quant WebUI low-memory remediation (第一阶段 4.1).

模拟真实 WebUI 客户端行为：
- 登录（获取 access_token）
- 建立 WebSocket（单连接，发送 PING 心跳，验证 PONG）
- 按真实频率轮询接口（5s 快刷新 / 60s 慢刷新）
- 记录请求次数、并发数、错误、响应时间、WS 重连次数

凭据只从环境变量读取，绝不输出 Token 或密码。

用法：
  export SOAK_URL=http://127.0.0.1:8080
  export SOAK_USER=ckquant
  export SOAK_PASS=ckquant123
  python scripts/soak_webui_low_memory.py --duration 1800

安全阈值（默认自动停止，防止把 VPS 打挂）：
  --max-container-gib 1.1   容器超过 1.1 GiB 停止
  --min-host-free-mib 250   主机可用内存低于 250 MiB 停止
"""
import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime

import aiohttp

log = logging.getLogger("soak")

# 与前端一致的轮询频率
FAST_INTERVAL = 5.0
SLOW_INTERVAL = 60.0
WS_HEARTBEAT_INTERVAL = 30.0
WS_PONG_TIMEOUT = 60.0

# 慢刷新接口（4.6 优化后的调用清单）
SLOW_ENDPOINTS = [
    "/api/v1/show_config",
    "/api/v1/profit_all",
    "/api/v1/balance",
    "/api/v1/historic_balance",
    "/api/v1/whitelist",
    "/api/v1/blacklist",
]
FAST_ENDPOINTS = [
    "/api/v1/status",
    "/api/v1/locks",
]


class SoakStats:
    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.responses: list[float] = []
        self.status_counts: Counter = Counter()
        self.ws_connects = 0
        self.ws_reconnects = 0
        self.ws_pongs = 0
        self.ws_messages = 0
        self.last_ws_pong_at = 0.0
        self.concurrency_peak = 0
        self._active = 0

    def request_start(self):
        self._active += 1
        self.concurrency_peak = max(self.concurrency_peak, self._active)

    def request_end(self, status: int, elapsed: float):
        self._active -= 1
        self.requests += 1
        self.status_counts[status] += 1
        self.responses.append(elapsed)
        if status >= 400:
            self.errors += 1

    def summary(self) -> str:
        if not self.responses:
            return "no requests"
        avg = sum(self.responses) / len(self.responses)
        p95 = sorted(self.responses)[int(len(self.responses) * 0.95) - 1]
        return (
            f"req={self.requests} errors={self.errors} avg={avg:.2f}s p95={p95:.2f}s "
            f"status={dict(self.status_counts)} ws_connects={self.ws_connects} "
            f"ws_reconnects={self.ws_reconnects} ws_pongs={self.ws_pongs} "
            f"ws_msgs={self.ws_messages} concurrency_peak={self.concurrency_peak}"
        )


class SoakClient:
    """一个模拟 WebUI 标签页：登录 + WS + 双频轮询。"""

    def __init__(self, base_url: str, user: str, password: str, stats: SoakStats):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.stats = stats
        self.token = ""
        self.session: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.stop_event = asyncio.Event()

    async def login(self) -> bool:
        async with aiohttp.ClientSession() as s:
            try:
                async with s.post(
                    f"{self.base_url}/api/v1/token/login",
                    auth=aiohttp.BasicAuth(self.user, self.password),
                ) as resp:
                    if resp.status != 200:
                        log.error(f"登录失败: HTTP {resp.status}")
                        return False
                    data = await resp.json()
                    self.token = data.get("access_token", "")
                    if not self.token:
                        log.error("登录响应无 access_token")
                        return False
                    return True
            except Exception as e:
                log.error(f"登录异常: {e}")
                return False

    async def _ws_token_url(self) -> str:
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        return f"{ws_url}/api/v1/message/ws?token={self.token}"

    async def run_websocket(self):
        """WS 主循环：连接 → 订阅 → 30s PING → 60s 无 PONG 判定超时重连。"""
        ws_url = await self._ws_token_url()
        while not self.stop_event.is_set():
            try:
                async with self.session.ws_connect(ws_url) as ws:
                    self.ws = ws
                    self.stats.ws_connects += 1
                    # 订阅（与前端一致）
                    await ws.send_json(
                        {
                            "type": "subscribe",
                            "data": [
                                "whitelist",
                                "entry_fill",
                                "exit_fill",
                                "entry_cancel",
                                "exit_cancel",
                            ],
                        }
                    )
                    self.stats.last_ws_pong_at = time.time()
                    last_ping = time.time()

                    async def _reader():
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                self.stats.ws_messages += 1
                                try:
                                    data = json.loads(msg.data)
                                    if data.get("type") == "pong":
                                        self.stats.ws_pongs += 1
                                        self.stats.last_ws_pong_at = time.time()
                                except json.JSONDecodeError:
                                    pass
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break

                    reader_task = asyncio.create_task(_reader())
                    try:
                        while not self.stop_event.is_set():
                            await asyncio.sleep(1)
                            now = time.time()
                            if now - last_ping >= WS_HEARTBEAT_INTERVAL:
                                try:
                                    await ws.send_json({"type": "ping"})
                                except Exception:
                                    pass
                                last_ping = now
                            # 60s 无 PONG → 判定连接已死，主动重连
                            if now - self.stats.last_ws_pong_at > WS_PONG_TIMEOUT:
                                log.warning("WS 60s 无 PONG，主动重连")
                                self.stats.ws_reconnects += 1
                                break
                    finally:
                        reader_task.cancel()
                        try:
                            await reader_task
                        except asyncio.CancelledError:
                            pass
            except Exception as e:
                log.warning(f"WS 连接异常: {e}")
                self.stats.ws_reconnects += 1
                await asyncio.sleep(5)

    async def _get(self, path: str):
        self.stats.request_start()
        start = time.time()
        try:
            async with self.session.get(
                f"{self.base_url}{path}", headers={"Authorization": f"Bearer {self.token}"}
            ) as resp:
                self.stats.request_end(resp.status, time.time() - start)
        except Exception as e:
            self.stats.request_end(0, time.time() - start)
            log.debug(f"请求异常 {path}: {e}")

    async def run_fast_poll(self):
        while not self.stop_event.is_set():
            for ep in FAST_ENDPOINTS:
                await self._get(ep)
            await asyncio.sleep(FAST_INTERVAL)

    async def run_slow_poll(self):
        while not self.stop_event.is_set():
            for ep in SLOW_ENDPOINTS:
                await self._get(ep)
            await asyncio.sleep(SLOW_INTERVAL)

    async def run(self):
        self.session = aiohttp.ClientSession()
        try:
            if not await self.login():
                return
            tasks = [
                asyncio.create_task(self.run_websocket()),
                asyncio.create_task(self.run_fast_poll()),
                asyncio.create_task(self.run_slow_poll()),
            ]
            await self.stop_event.wait()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await self.session.close()


def read_container_usage(container: str) -> float:
    """返回容器内存 GiB，失败返回 0。"""
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # 输出形如 "483.6MiB / 1.575GiB"
        part = out.stdout.strip().split(" / ")[0]
        if part.endswith("MiB"):
            return float(part[:-3]) / 1024
        if part.endswith("GiB"):
            return float(part[:-3])
        if part.endswith("KiB"):
            return float(part[:-3]) / 1024 / 1024
    except Exception:
        pass
    return 0.0


def host_free_mib() -> float:
    """返回主机可用内存 MiB（Linux）。"""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return float(line.split()[1]) / 1024
    except Exception:
        pass
    return float("inf")


async def main():
    parser = argparse.ArgumentParser(description="CK_Quant WebUI soak test")
    parser.add_argument("--duration", type=int, default=1800, help="运行秒数（默认 1800 = 30 分钟）")
    parser.add_argument("--container", default="CK_Quant", help="docker 容器名")
    parser.add_argument("--max-container-gib", type=float, default=1.1, help="容器内存安全上限 GiB")
    parser.add_argument("--min-host-free-mib", type=float, default=250, help="主机可用内存下限 MiB")
    parser.add_argument("--log-file", default="", help="每 60 秒追加一行指标到此文件")
    args = parser.parse_args()

    url = os.environ.get("SOAK_URL", "")
    user = os.environ.get("SOAK_USER", "")
    password = os.environ.get("SOAK_PASS", "")
    if not (url and user and password):
        print("错误：必须设置 SOAK_URL / SOAK_USER / SOAK_PASS 环境变量")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()],
    )

    stats = SoakStats()
    client = SoakClient(url, user, password, stats)
    task = asyncio.create_task(client.run())

    start = time.time()
    baseline = read_container_usage(args.container)
    log.info(f"soak 开始: duration={args.duration}s 容器基线={baseline:.2f}GiB")
    log_file = open(args.log_file, "a") if args.log_file else None
    if log_file:
        log_file.write(f"ts,container_gib,host_free_mib,{stats.summary()}\n")

    try:
        while time.time() - start < args.duration:
            await asyncio.sleep(60)
            elapsed = int(time.time() - start)
            usage = read_container_usage(args.container)
            free = host_free_mib()
            line = (
                f"[{elapsed}s] 容器={usage:.2f}GiB 主机可用={free:.0f}MiB | {stats.summary()}"
            )
            log.info(line)
            if log_file:
                log_file.write(
                    f"{datetime.now().isoformat()},{usage:.3f},{free:.0f},{stats.summary()}\n"
                )
                log_file.flush()
            # 安全阈值：自动停止
            if usage > args.max_container_gib:
                log.error(f"容器内存 {usage:.2f}GiB 超过阈值 {args.max_container_gib}GiB，停止")
                break
            if free < args.min_host_free_mib:
                log.error(f"主机可用内存 {free:.0f}MiB 低于阈值，停止")
                break
            # 内存阶梯增长检查：净增长超过 50MiB 且单调上涨（第一阶段通过标准）
            if elapsed >= 1800 and usage - baseline > 0.05:
                log.warning(
                    f"30 分钟后容器内存净增长 {usage - baseline:.2f}GiB > 50MiB，"
                    "未达到第一阶段通过标准"
                )
    finally:
        client.stop_event.set()
        await task
        log.info(f"soak 结束 | {stats.summary()}")
        if log_file:
            log_file.close()


if __name__ == "__main__":
    asyncio.run(main())
