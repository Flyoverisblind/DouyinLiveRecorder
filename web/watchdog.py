# -*- coding: utf-8 -*-

"""
控制台看门狗（无窗口版）。

由计划任务通过 pythonw.exe 调用：pythonw.exe 本身不带控制台，
所以每次检查不会弹窗，做到「无感」。

职责：
1. 控制台端口没在监听 -> 启动 web/server.py
2. 控制台活着但录制进程没跑 -> 调 /api/control/start
3. 一切正常 -> 什么都不做，只记一行日志（可关闭静默）

日志：logs/watchdog.log
手动执行：双击 控制台看门狗.bat（等同运行本脚本）
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(ROOT, 'logs', 'watchdog.log')
PID_FILE = os.path.join(ROOT, 'logs', 'console.pid')
DEFAULT_PORT = 8765
START_WAIT = 20          # 启动控制台后最多等这么多秒
LOG_WHEN_OK = True       # 一切正常时也记一行（便于确认它确实在跑）


def log(message: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        stamp = time.strftime('%Y/%m/%d %H:%M:%S')
        with open(LOG_FILE, 'a', encoding='utf-8') as fp:
            fp.write(f'[{stamp}] {message}\n')
    except OSError:
        pass


def read_port() -> int:
    """从 console.pid 里读实际端口（端口被占用时会顺延）。"""
    try:
        parts = open(PID_FILE, encoding='utf-8').read().split()
        return int(parts[1])
    except (OSError, ValueError, IndexError):
        return DEFAULT_PORT


def port_open(port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def api_get(port: int, path: str, timeout: float = 5.0):
    url = f'http://127.0.0.1:{port}{path}'
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def api_post(port: int, path: str, payload: dict = None, timeout: float = 10.0):
    body = json.dumps(payload or {}).encode('utf-8')
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}{path}', data=body,
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def pythonw_path() -> str:
    candidate = os.path.join(ROOT, '.venv', 'Scripts', 'pythonw.exe')
    if os.path.isfile(candidate):
        return candidate
    # 退化到同目录的 pythonw / 当前解释器
    fallback = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    return fallback if os.path.isfile(fallback) else sys.executable


def start_console() -> bool:
    cmd = [pythonw_path(), os.path.join('web', 'server.py')]
    flags = 0
    if os.name == 'nt':
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | \
            getattr(subprocess, 'DETACHED_PROCESS', 0)
    try:
        subprocess.Popen(cmd, cwd=ROOT, creationflags=flags,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         close_fds=True)
    except OSError as exc:
        log(f'启动控制台失败: {exc}')
        return False

    deadline = time.time() + START_WAIT
    while time.time() < deadline:
        # 端口可能因占用而顺延，所以每轮重新读 pid 文件
        if port_open(read_port()):
            log('控制台未运行，已启动')
            return True
        time.sleep(0.5)
    log(f'已尝试启动控制台，但 {START_WAIT} 秒内端口仍未监听')
    return False


def ensure_recorder(port: int) -> None:
    try:
        state = api_get(port, '/api/state')
    except Exception as exc:                      # noqa: BLE001
        log(f'查询录制状态失败: {type(exc).__name__}: {exc}')
        return
    process = state.get('process') or {}
    if process.get('running'):
        if LOG_WHEN_OK:
            log(f'控制台与录制均正常（录制 PID {process.get("pid")}）')
        return
    try:
        result = api_post(port, '/api/control/start')
        if result.get('ok'):
            log(f'录制进程未运行，已自动启动（PID {result.get("pid")}）')
        else:
            log(f'录制进程未运行，启动失败: {result.get("error")}')
    except Exception as exc:                      # noqa: BLE001
        log(f'启动录制失败: {type(exc).__name__}: {exc}')


def main() -> int:
    port = read_port()
    if not port_open(port):
        if not start_console():
            return 1
        port = read_port() or port
        # 等接口真正可用（进程起了但还没 bind 完）
        for _ in range(20):
            try:
                api_get(port, '/api/ping', timeout=2)
                break
            except Exception:                     # noqa: BLE001
                time.sleep(0.5)
    ensure_recorder(port)
    return 0


if __name__ == '__main__':
    sys.exit(main())
