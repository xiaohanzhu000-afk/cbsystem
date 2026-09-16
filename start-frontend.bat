@echo off
chcp 65001 >nul
cd /d "%~dp0frontend"
echo [1/2] 安装依赖...
call npm install
echo [2/2] 启动前端 http://127.0.0.1:5173
call npm run dev
pause
