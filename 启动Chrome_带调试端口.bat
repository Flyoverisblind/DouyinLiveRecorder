@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title 以调试模式启动 Chrome（供控制台同步 Cookie）

set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
    echo.
    echo [x] 没有找到 Chrome，请手动修改本文件里的 CHROME 路径。
    echo.
    pause
    exit /b 1
)

tasklist /FI "IMAGENAME eq chrome.exe" 2>nul | find /I "chrome.exe" >nul
if not errorlevel 1 (
    echo.
    echo [!] 检测到 Chrome 正在运行。
    echo     浏览器已经在跑时，--remote-debugging-port 参数会被忽略，
    echo     所以必须先完全关闭 Chrome 才能带上调试端口。
    echo.
    choice /C YN /N /M "现在帮你关闭 Chrome 并重新启动？(Y=是 / N=否) "
    if errorlevel 2 (
        echo.
        echo 已取消。请手动完全退出 Chrome 后再运行本文件。
        echo.
        pause
        exit /b 1
    )
    echo 正在关闭 Chrome ...
    taskkill /IM chrome.exe /T /F >nul 2>&1
    timeout /t 3 >nul
)

echo.
echo 正在以调试端口 9222 启动 Chrome ...
start "" "%CHROME%" --remote-debugging-port=9222
timeout /t 4 >nul

netstat -ano | find ":9222" | find "LISTENING" >nul
if errorlevel 1 (
    echo.
    echo [x] 端口 9222 没有起来，可能 Chrome 仍有余留进程。
    echo     请打开任务管理器，结束所有 chrome.exe 后再试。
    echo.
) else (
    echo.
    echo [OK] 调试端口 9222 已就绪。
    echo      现在回到控制台点右上角的 Cookie 图标即可同步。
    echo      注意：这个 Chrome 窗口不要关，关了端口就没了。
    echo.
)
pause
