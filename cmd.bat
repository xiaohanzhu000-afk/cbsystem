@echo off
:: 启动项目1
start "" cmd /k "cd /d C:\Users\3013806\Desktop\cbsystem\backend && python -m uvicorn main:app --reload --port 8024"
:: 启动项目2
start "" cmd /k "cd /d C:\Users\3013806\Desktop\cbsystem\frontend && npm run dev"
:: 启动项目3
start "" cmd /k "cd /d C:\Users\3013806\Documents\Code\neworld-register\cbserver && npm run dev"
:: 启动项目3
start "" cmd /k "cd /d C:\Users\3013806\Documents\Code\neworld-register && npm run dev"

