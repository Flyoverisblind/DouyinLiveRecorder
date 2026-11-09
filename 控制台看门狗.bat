@echo off
chcp 936 >nul
setlocal
title 控制台看门狗（手动检查）

rem 计划任务用的是 pythonw.exe 直接跑 web\watchdog.py（无窗口）。
rem 这个 .bat 只是给你手动检查用的：跑完会显示结果，方便确认。

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo 正在检查控制台与录制进程 ...
echo.
"%PY%" "%ROOT%\web\watchdog.py"
set "CODE=%ERRORLEVEL%"
echo.
echo --- logs\watchdog.log 最后 5 行 ---
powershell -NoProfile -Command "if (Test-Path '%ROOT%\logs\watchdog.log') { Get-Content '%ROOT%\logs\watchdog.log' -Tail 5 } else { '(还没有日志)' }"
echo.
if "%CODE%"=="0" (echo 检查完成。) else (echo 检查过程中有失败，退出码 %CODE%。)
echo.
pause
