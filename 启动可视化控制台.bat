@echo off
cd /d "%~dp0"
title DouyinLiveRecorder 可视化控制台

echo ==============================================================
echo   DouyinLiveRecorder 可视化控制台
echo ==============================================================
echo.

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY call :find_python
if not defined PY goto :no_python

echo 使用的解释器: %PY%
"%PY%" -c "import requests, loguru, httpx, execjs" >nul 2>nul
if not errorlevel 1 goto :run

echo.
echo [提示] 检测到缺少运行依赖，正在安装 requirements.txt ...
echo        如果安装失败，请手动执行:  %PY% -m pip install -r requirements.txt
echo.
"%PY%" -m pip install -r requirements.txt
echo.

:run
echo 正在启动控制台，浏览器会自动打开 ...
echo 关闭本窗口即可退出控制台（录制中请先在网页上点「停止」）。
echo.
"%PY%" web\server.py --open %*
echo.
echo 控制台已退出。
pause
exit /b 0

:find_python
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
exit /b 0

:no_python
echo [错误] 没有找到 Python 3.10 或更高版本。
echo        请先安装 Python 并在安装时勾选 "Add Python to PATH"。
echo        下载地址: https://www.python.org/downloads/
echo.
pause
exit /b 1
