# -*- coding: utf-8 -*-
"""
B 站扫码登录：生成二维码 → 轮询结果 → 直接拿到登录 Cookie。

走 B 站官方 passport 接口，完全不碰浏览器，因此没有 cookie 库独占锁、
也没有 v20(App-Bound) 解密的限制：

1. GET /x/passport-login/web/qrcode/generate
   -> { qrcode_key, url }
2. 把 url 渲染成二维码（segno，纯 Python）交给用户扫
3. GET /x/passport-login/web/qrcode/poll?qrcode_key=...
   -> data.code: 0 成功 / 86101 未扫码 / 86090 已扫码待确认 / 86038 已失效
   成功时响应头 Set-Cookie 里就是 SESSDATA 等登录态

二维码有效期约 180 秒，过期后重新生成即可。
"""

import http.cookies
import json

import requests

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

HEADERS = {
    'User-Agent': UA,
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'origin': 'https://www.bilibili.com',
    'referer': 'https://www.bilibili.com/',
}

GENERATE_API = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate'
POLL_API = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
NAV_API = 'https://api.bilibili.com/x/web-interface/nav'

# 拼 Cookie 时的字段顺序，便于比对与阅读
COOKIE_ORDER = (
    'SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'sid',
    'buvid3', 'buvid4', 'bili_ticket', 'bili_ticket_expires',
    'CURRENT_QUALITY', 'CURRENT_FNVAL',
)

# 轮询状态码
STATE_SUCCESS = 0
STATE_WAITING = 86101        # 未扫码
STATE_SCANNED = 86090        # 已扫码，等待手机端确认
STATE_EXPIRED = 86038        # 二维码已失效


def qr_svg_data_uri(content: str) -> str:
    """把文本渲染成 SVG data URI（前端直接塞进 <img src>）。"""
    try:
        import segno
    except ImportError:
        return ''
    return segno.make(content, error='m').svg_data_uri()


def generate() -> dict:
    """申请一个登录二维码。返回 {ok, key, url, image, error}。"""
    try:
        resp = requests.get(GENERATE_API, headers=HEADERS, timeout=15)
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': f'申请二维码失败：{exc}'}

    data = payload.get('data') or {}
    key = data.get('qrcode_key') or ''
    url = data.get('url') or ''
    if payload.get('code') != 0 or not key or not url:
        return {'ok': False,
                'error': f"申请二维码失败：{payload.get('message') or '返回内容异常'}"}

    image = qr_svg_data_uri(url)
    if not image:
        return {'ok': False, 'key': key, 'url': url,
                'error': '缺少 segno 库，无法生成二维码（pip install segno）'}
    return {'ok': True, 'key': key, 'url': url, 'image': image, 'expires_in': 180}


def _extract_cookies(resp) -> dict:
    """从响应头里收集 Set-Cookie。

    不能用 resp.headers['Set-Cookie'] 直接切分：Expires 属性本身带逗号，
    只能逐个 Set-Cookie 头解析。
    """
    raw_headers = []
    try:
        raw_headers = resp.raw.headers.getlist('Set-Cookie')
    except Exception:  # noqa: BLE001 - 某些适配器不支持 getlist
        raw_headers = []

    jar = {}
    for raw in raw_headers:
        try:
            parsed = http.cookies.SimpleCookie()
            parsed.load(raw)
        except Exception:  # noqa: BLE001
            continue
        for name, morsel in parsed.items():
            if morsel.value:
                jar[name] = morsel.value

    # 兜底：requests 自己解析出的 cookie
    try:
        for name, value in resp.cookies.get_dict().items():
            jar.setdefault(name, value)
    except Exception:  # noqa: BLE001
        pass
    return jar


def build_cookie_header(jar: dict) -> str:
    ordered = [f'{name}={jar[name]}' for name in COOKIE_ORDER if jar.get(name)]
    extras = [f'{name}={value}' for name, value in jar.items()
              if name not in COOKIE_ORDER and value]
    return '; '.join(ordered + extras)


def verify(cookie: str, timeout: int = 15) -> dict:
    """调 nav 接口确认登录态。"""
    if not cookie:
        return {'ok': False, 'login': False, 'error': 'Cookie 为空'}
    try:
        resp = requests.get(NAV_API, headers={**HEADERS, 'Cookie': cookie}, timeout=timeout)
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'login': False, 'error': f'校验失败：{exc}'}

    if payload.get('code') == -101:
        return {'ok': True, 'login': False, 'error': 'Cookie 无效（未登录）'}
    data = payload.get('data') or {}
    return {
        'ok': True,
        'login': bool(data.get('isLogin')),
        'uname': data.get('uname') or '',
        'vip': (data.get('vip_label') or {}).get('text', ''),
    }


def poll(qrcode_key: str) -> dict:
    """查询扫码状态。

    返回 {ok, state, cookie, uname, vip, error}
      state: waiting / scanned / expired / success / failed
    """
    if not qrcode_key:
        return {'ok': False, 'state': 'failed', 'error': '缺少 qrcode_key'}

    try:
        resp = requests.get(POLL_API, params={'qrcode_key': qrcode_key},
                            headers=HEADERS, timeout=15)
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'state': 'failed', 'error': f'轮询失败：{exc}'}

    data = payload.get('data') or {}
    code = data.get('code')
    if code == STATE_WAITING:
        return {'ok': True, 'state': 'waiting'}
    if code == STATE_SCANNED:
        return {'ok': True, 'state': 'scanned'}
    if code == STATE_EXPIRED:
        return {'ok': True, 'state': 'expired'}
    if code != STATE_SUCCESS:
        message = data.get('message') or payload.get('message') or f'未知状态码 {code}'
        return {'ok': False, 'state': 'failed', 'error': message}

    jar = _extract_cookies(resp)
    cookie = build_cookie_header(jar)
    if not jar.get('SESSDATA'):
        return {'ok': False, 'state': 'failed',
                'error': '登录成功但没拿到 SESSDATA，请重试'}

    check = verify(cookie)
    if not check.get('login'):
        return {'ok': False, 'state': 'failed',
                'error': check.get('error') or '拿到的 Cookie 校验未通过'}
    return {'ok': True, 'state': 'success', 'cookie': cookie,
            'uname': check.get('uname', ''), 'vip': check.get('vip', '')}


def write_cookie(config_path: str, cookie: str) -> dict:
    """把 Cookie 写回 config.ini（走 config_store，保住注释与大小写）。"""
    import os
    import sys

    web_dir = os.path.dirname(os.path.abspath(__file__))
    if web_dir not in sys.path:
        sys.path.insert(0, web_dir)
    try:
        import config_store
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': f'无法加载 config_store：{exc}'}

    try:
        result = config_store.update_config_file(
            config_path, {'Cookie': {'B站cookie': cookie}})
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': f'写入配置失败：{exc}'}
    return {'ok': True, 'changed': result.get('changed', [])}


if __name__ == '__main__':
    import sys

    info = generate()
    if not info.get('ok'):
        print('生成失败:', info.get('error'))
        sys.exit(1)
    print('二维码内容:', info['url'])
    print('SVG 长度:', len(info['image']))
    print('qrcode_key:', info['key'])
    print('（用手机 B 站扫码后，poll 会返回 success）')
