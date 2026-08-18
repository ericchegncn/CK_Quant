@echo off
chcp 65001 >nul
title CK Quant Desktop
cd /d "%~dp0"
echo ========================================
echo   CK Quant Desktop 启动中...
echo ========================================
echo.
where npx >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Node.js，请先安装: https://nodejs.org
    pause
    exit /b 1
)
if not exist "node_modules\electron\dist\electron.exe" (
    echo [首次运行] 正在安装依赖，请稍候...
    call npx pnpm@latest install
    node node_modules/electron/install.js
)
echo [启动] 正在打开桌面版...
start "" node_modules\.bin\electron.cmd .
exit /b 0
