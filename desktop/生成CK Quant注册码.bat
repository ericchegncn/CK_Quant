@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "node_modules\.bin\electron.cmd" (
  echo 尚未安装桌面版开发依赖，请先在 desktop 目录安装依赖。
  pause
  exit /b 1
)
call "node_modules\.bin\electron.cmd" "tools\license-admin.js"
