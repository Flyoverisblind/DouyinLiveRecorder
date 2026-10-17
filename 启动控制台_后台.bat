@echo off
cd /d "%~dp0"
title DouyinLiveRecorder 控制台 - 后台运行
setlocal enabledelayedexpansion

echo ==============================================================
echo   DouyinLiveRecorder 可视化控制台 - 后台运行
echo ==============================================================
echo.

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY call :find_python
if not defined PY goto :no_python

rem 优先用 pythonw.exe：它没有控制台窗口，关掉本窗口完全影响不到它
set "PYW="
if exist ".venv\Scripts\pythonw.exe" set "PYW=.venv\Scripts\pythonw.exe"
if not defined PYW if exist "venv\Scripts\pythonw.exe" set "PYW=venv\Scripts\pythonw.exe"
if not defined PYW set "PYW=%PY%"

echo 使用的解释器: %PY%
echo 后台解释器:   %PYW%
echo.

"%PY%" -c "import requests, loguru, httpx, execjs" >nul 2>nul
if errorlevel 1 (
  echo [提示] 检测到缺少运行依赖，正在安装 requirements.txt ...
  echo        如果安装失败，请手动执行:  %PY% -m pip install -r requirements.txt
  echo.
  "%PY%" -m pip install -r requirements.txt
  echo.
)

rem 清掉上一次残留的 pid 标记，避免读到旧端口
if exist "logs\console.pid" del "logs\console.pid" >nul 2>nul

echo 正在后台启动控制台 ...
start "" "%PYW%" web\server.py --open %*

rem 等它把 pid 和端口写进 logs\console.pid
set /a WAIT=0
:waitpid
if exist "logs\console.pid" goto :ready
set /a WAIT+=1
if !WAIT! geq 20 goto :timeout
ping -n 2 127.0.0.1 >nul
goto :waitpid

:ready
ping -n 2 127.0.0.1 >nul
set "CSPID="
set "CPORT="
set /a IDX=0
for /f "usebackq delims=" %%a in ("logs\console.pid") do (
  set /a IDX+=1
  if !IDX! equ 1 set "CSPID=%%a"
  if !IDX! equ 2 set "CPORT=%%a"
)

echo.
echo 启动成功，进程 PID !CSPID!
echo.
echo   访问地址: http://127.0.0.1:!CPORT!/
echo.
echo 浏览器会自动打开。本窗口可以直接关掉，控制台会继续在后台运行。
echo 要停止控制台，请双击「停止控制台_后台.bat」。
echo.
pause
exit /b 0

:timeout
echo.
echo [警告] 40 秒内没等到启动标记，控制台可能没起来。
echo        请查看 logs\console.log 里的错误信息。
echo.
pause
exit /b 1

:find_python
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
exit /b 0

:no_python
echo [错误] 没有找到 Python 3.10 或更高版本。
echo        请先安装 Python 并在安装时勾选 Add Python to PATH。
echo.
pause
exit /b 1
