# 私有策略安全边界

CK Quant 的应用代码与交易策略必须分离发布。

- 私有策略只保存在部署主机的 `user_data/strategies/`。
- Docker 通过运行时 volume 挂载读取策略，官方镜像不得内置任何私有策略。
- Git 忽略私有策略、策略研究脚本、实盘 SSH 运维脚本和 CK 专用测试。
- Docker 构建上下文排除 `user_data/`、`scripts/`、策略目录及 `CK_*.py`。
- Dockerfile 在构建阶段再次检查；发现疑似私有策略源码时立即失败。
- GitHub Privacy Guard 会阻止私有策略路径或 CK 策略导入进入公开分支。

APK 仅包含 WebUI 与移动端壳，不包含 Python 策略源码。
