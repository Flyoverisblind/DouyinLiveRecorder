@echo off
cd /d "%~dp0"
title DouyinLiveRecorder 停止后台控制台
setlocal enabledelayedexpansion

set "PIDFILE=logs\console.pid"

echo ==============================================================
echo   DouyinLiveRecorder 停止后台控制台
echo ==============================================================
echo.

if not exist "%PIDFILE%" goto :notrunning

set "CSPID="
set "CPORT="
set /a IDX=0
for /f "usebackq delims=" %%a in ("%PIDFILE%") do (
  set /a IDX+=1
  if !IDX! equ 1 set "CSPID=%%a"
  if !IDX! equ 2 set "CPORT=%%a"
)
if not defined CSPID goto :notrunning

rem 用命令行双重确认，避免 PID 被系统复用后误杀别的进程
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process -Filter 'ProcessId=%CSPID%' | Where-Object { $_.CommandLine -like '*web*server.py*' }) { exit 0 } else { exit 1 }" >nul 2>nul
if errorlevel 1 goto :stale

echo 正在停止控制台，PID %CSPID%，端口 %CPORT% ...
echo.
echo 先让网页端优雅地停止录制，避免强制结束写坏正在录制的文件 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:%CPORT%/api/control/stop' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 15; if ($r.ok) { Write-Host '  已停止录制进程' } else { Write-Host '  当前没有在录制' } } catch { Write-Host '  当前没有在录制' }"

echo 正在结束控制台进程树 ...
taskkill /PID %CSPID% /T /F >nul 2>nul
ping -n 2 127.0.0.1 >nul

if exist "%PIDFILE%" del "%PIDFILE%" >nul 2>nul
echo.
echo 控制台已停止。
echo.
pause
exit /b 0

:stale
if exist "%PIDFILE%" del "%PIDFILE%" >nul 2>nul
echo 记录里的进程已经不在了，控制台应该早就关了，已清理残留标记。
echo.
pause
exit /b 0

:notrunning
echo 没有找到正在运行的后台控制台。
echo 如果你是用「启动可视化控制台.bat」前台启动的，直接关那个窗口就行。
echo.
pause
exit /b 0
