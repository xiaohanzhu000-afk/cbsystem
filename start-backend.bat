@echo off
chcp 65001 >nul
cd /d "%~dp0backend"
echo [1/2] 安装依赖...
python -m pip install -r requirements.txt
echo [2/2] 启动后端 http://127.0.0.1:8024
python -m uvicorn main:app --reload --port 8024
pause
