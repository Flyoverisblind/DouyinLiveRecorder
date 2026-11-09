@echo off
chcp 936 >nul
setlocal
rem ===================================================================
rem  控制台看门狗：由计划任务每 5 分钟调用一次
rem  1) 8765 端口没有监听 -> 启动控制台
rem  2) 控制台起来后，录制进程没在跑 -> 调接口启动录制
rem  日志：logs\watchdog.log
rem ===================================================================
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "LOG=%ROOT%logs\watchdog.log"
if not exist "%ROOT%logs" mkdir "%ROOT%logs"

rem ---- 端口是否在监听
netstat -ano | findstr /R /C:":8765[ ]" | findstr /I "LISTENING" >nul
if not errorlevel 1 goto check_recorder

echo [%date% %time%] 控制台未运行，正在启动 >> "%LOG%"
start "" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%web\server.py"
rem 等控制台把端口开起来（最多 20 秒）
for /l %%i in (1,1,20) do (
    timeout /t 1 >nul
    netstat -ano | findstr /R /C:":8765[ ]" | findstr /I "LISTENING" >nul
    if not errorlevel 1 goto check_recorder
)
echo [%date% %time%] 启动后端口仍未监听，等待下次检查 >> "%LOG%"
exit /b 1

:check_recorder
rem ---- 录制进程是否在跑（靠 /api/state 判断）
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $s = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/state' -TimeoutSec 8; if (-not $s.process.running) { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/api/control/start' -ContentType 'application/json' -Body '{}' -TimeoutSec 30 | Out-Null; Write-Output 'started' } } catch { }" > "%TEMP%\dlr_watchdog_tmp.txt" 2>nul
findstr /I "started" "%TEMP%\dlr_watchdog_tmp.txt" >nul
if not errorlevel 1 echo [%date% %time%] 录制进程未运行，已自动启动 >> "%LOG%"
del "%TEMP%\dlr_watchdog_tmp.txt" >nul 2>nul
exit /b 0
