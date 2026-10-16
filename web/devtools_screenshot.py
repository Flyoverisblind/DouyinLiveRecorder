# -*- coding: utf-8 -*-
"""
开发辅助工具：用无头 Chrome/Edge 给控制台各个页面截图。

之所以不用 `chrome --screenshot`，是因为「实时日志」页面会保持一条 SSE 长连接，
Chrome 永远不会进入网络空闲状态，命令会一直挂住。这里改用 CDP（Chrome DevTools
Protocol）逐个标签页打开、等待、截图、关闭。

依赖（仅本工具需要，不是运行控制台的依赖）：
    pip install websocket-client

用法：
    python web/devtools_screenshot.py --port 8765 --out web/screenshots
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import websocket  # type: ignore

CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
]

PAGES = [
    ('dashboard', '#/dashboard', 900),
    ('urls', '#/urls', 990),
    ('config-recording', '#/config/%E5%BD%95%E5%88%B6%E8%AE%BE%E7%BD%AE', 990),
    ('config-push', '#/config/%E6%8E%A8%E9%80%81%E9%85%8D%E7%BD%AE', 990),
    ('config-cookie', '#/config/Cookie', 990),
    ('logs', '#/logs', 800),
    ('files', '#/files', 620),
]

SKIP_TYPES = {'page', 'iframe', 'other', 'service_worker', 'shared_worker', 'worker', 'browser', 'webview'}


def find_browser() -> str:
    for path in CANDIDATES:
        if os.path.isfile(path):
            return path
    for name in ('google-chrome', 'chromium', 'chromium-browser', 'chrome', 'msedge'):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit('未找到 Chrome/Edge，无法截图')


def http_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def wait_for_devtools(port: int, timeout: float = 25.0) -> str:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            info = http_json(f'http://127.0.0.1:{port}/json/version')
            return info['webSocketDebuggerUrl']
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.4)
    raise SystemExit(f'DevTools 端口未就绪: {last}')


def open_target(port: int, url: str) -> str:
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}/json/new?{urllib.parse.quote(url, safe="")}',
        method='PUT',
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))['id']


def close_target(port: int, target_id: str) -> None:
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{port}/json/close/{target_id}', timeout=5).read()
    except Exception:  # noqa: BLE001
        pass


def capture(ws_url: str, out_path: str, width: int, height: int, wait: float, dark: bool = False) -> None:
    ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
    counter = {'id': 0}

    def send(method, params=None):
        counter['id'] += 1
        msg_id = counter['id']
        ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params or {}}))
        while True:
            raw = ws.recv()
            data = json.loads(raw)
            if data.get('id') == msg_id:
                if 'error' in data:
                    raise RuntimeError(f'{method} -> {data["error"]}')
                return data.get('result', {})

    try:
        send('Page.enable')
        send('Emulation.setDeviceMetricsOverride', {
            'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False,
        })
        if dark:
            send('Emulation.setEmulatedMedia', {
                'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}],
            })
            send('Page.reload', {'ignoreCache': False})
            time.sleep(1.0)
        time.sleep(wait)  # 等待前端渲染（含 SSE 首屏日志）
        result = send('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True})
        with open(out_path, 'wb') as fp:
            fp.write(base64.b64decode(result['data']))
    finally:
        ws.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765, help='控制台端口')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots'))
    parser.add_argument('--width', type=int, default=1500)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--wait', type=float, default=3.0, help='每个页面渲染等待秒数')
    parser.add_argument('--debug-port', type=int, default=9333)
    parser.add_argument('--dark', action='store_true', help='模拟系统深色模式')
    parser.add_argument('--prefix', default='', help='输出文件名前缀')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    browser = find_browser()
    profile = tempfile.mkdtemp(prefix='dlr_shot_')
    print(f'浏览器: {browser}')
    print(f'输出目录: {args.out}')

    proc = subprocess.Popen(
        [browser, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
         '--hide-scrollbars', '--disable-extensions', '--remote-allow-origins=*',
         f'--user-data-dir={profile}',
         f'--remote-debugging-port={args.debug_port}', f'--window-size={args.width},{args.height}',
         'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_devtools(args.debug_port)
        base = f'http://{args.host}:{args.port}/'
        for name, route, height in PAGES:
            url = base + route
            target_id = open_target(args.debug_port, url)
            time.sleep(0.8)
            targets = [t for t in http_json(f'http://127.0.0.1:{args.debug_port}/json/list')
                       if t.get('id') == target_id]
            if not targets:
                print(f'  [skip] {name}: 找不到标签页')
                continue
            out_path = os.path.join(args.out, f'{args.prefix}{name}.png')
            capture(targets[0]['webSocketDebuggerUrl'], out_path, args.width, height, args.wait, args.dark)
            size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
            print(f'  [ok] {args.prefix}{name}.png  {size} bytes')
            close_target(args.debug_port, target_id)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    print('截图完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
