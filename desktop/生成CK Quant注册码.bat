@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "CKQ_ELECTRON=%~dp0node_modules\electron\dist\electron.exe"
if not exist "%CKQ_ELECTRON%" (
  echo 尚未安装桌面版开发依赖，请先在 desktop 目录安装依赖。
  pause
  exit /b 1
)
"%CKQ_ELECTRON%" "%~dp0tools\license-admin.js"
if errorlevel 1 (
  echo.
  echo 注册码签发工具启动失败，错误代码：%errorlevel%
  pause
)
