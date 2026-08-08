# CK Quant 多语言 WebUI 与 Android 管理端

CK Quant 的 WebUI 和 Android 应用共用同一套界面与 API。支持简体中文、繁体中文、英语、德语、日语、法语和韩语；语言可在登录页菜单或设置页切换。

## 启用服务器管理

远程写入功能默认关闭。确认 API 使用强密码且公网入口已启用 HTTPS 后，在实际使用的配置文件中加入：

```json
"ck_quant_admin": {
    "enabled": true,
    "config_edit": true,
    "strategy_edit": true
}
```

重启 CK Quant 后，WebUI 和 Android 应用的“服务器管理”页面会自动启用。无需向容器挂载 Docker socket；“保存并重启机器人”使用 CK Quant 自身的安全重载流程。

## 安全机制

- 所有管理接口使用现有 API 登录和 JWT 身份验证。
- 只允许修改当前 `user_data` 内正在使用的主配置，以及 `user_data/strategies` 内正在运行的策略。
- API 密码、交易所密钥、Telegram token 等敏感值不会返回到编辑器；保存时自动保留服务器原值。
- 保存前执行 JSON/Python 语法和 CK Quant 配置一致性检查。
- 使用文件版本哈希避免两个设备互相覆盖修改。
- 每次保存前自动备份，并记录不含密钥的 JSONL 审计日志。
- 新配置重载失败时自动恢复旧文件并再次尝试恢复运行。
- 管理页可查看最近 50 个备份并恢复配置或策略。

备份位于 `user_data/backups/ck_quant_admin/`，审计日志位于 `user_data/logs/ck_quant_admin_audit.jsonl`。

## Android 应用

应用支持登录多个 CK Quant 服务器、查看收益/持仓/订单、强制开仓和平仓、启动或停止机器人，以及修改和恢复配置与策略。登录 token 使用 Android Keystore 的 AES-GCM 密钥加密保存，退出最后一个服务器时会清除加密记录。

服务器地址应填写可由手机访问的根地址，例如 `https://quant.example.com`，不要填写 `/api/v1`。生产环境强烈建议使用受信任证书的 HTTPS；应用保留 HTTP 支持仅用于可信局域网调试。

## 构建

Android 工程位于 `ck_quant_ui/android/`。WebUI 修改后运行：

```powershell
cd ck_quant_ui
pnpm android:sync
cd android
./gradlew assembleDebug
```

生成的开发 APK 位于 `ck_quant_ui/android/app/build/outputs/apk/debug/app-debug.apk`。
