@echo off
chcp 936 >nul
setlocal
set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
    echo.
    echo 没有找到 Chrome，请手动修改本文件里的路径。
    echo.
    pause
    exit /b 1
)
echo 正在以「可调试」方式启动 Chrome（端口 9222）...
echo.
echo 注意：如果 Chrome 已经在运行，这个参数会被忽略！
echo       请先完全退出 Chrome（任务栏图标也要退），再运行本文件。
echo.
start "" "%CHROME%" --remote-debugging-port=9222
timeout /t 3 >nul
echo 已启动。现在可以回到控制台点 Cookie 按钮同步。
pause
