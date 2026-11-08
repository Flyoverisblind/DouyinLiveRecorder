# -*- coding: utf-8 -*-
"""
B 站扫码登录模块自检（不联网：requests.get 被替换为假响应）。

用法： python web/selftest_bili_login.py
"""
import os
import sys

WEB = os.path.dirname(os.path.abspath(__file__))
if WEB not in sys.path:
    sys.path.insert(0, WEB)

import bili_login  # noqa: E402

failures = []


def check(name, ok, detail=''):
    print(f'  [{"OK  " if ok else "FAIL"}] {name}{"" if ok else "  -> " + str(detail)}')
    if not ok:
        failures.append(name)


class FakeHeaders:
    def __init__(self, set_cookies):
        self._set_cookies = set_cookies

    def getlist(self, name):
        return self._set_cookies if name == 'Set-Cookie' else []


class FakeRaw:
    def __init__(self, set_cookies):
        self.headers = FakeHeaders(set_cookies)


class FakeCookies:
    def __init__(self, mapping=None):
        self._mapping = mapping or {}

    def get_dict(self):
        return dict(self._mapping)


class FakeResp:
    def __init__(self, payload=None, set_cookies=None, cookies=None):
        self._payload = payload or {}
        self.raw = FakeRaw(set_cookies or [])
        self.cookies = FakeCookies(cookies)

    def json(self):
        return self._payload


print('[1] Set-Cookie 解析')
resp = FakeResp(set_cookies=[
    'SESSDATA=abc%2C123%2Cxyz; Path=/; Domain=.bilibili.com; Expires=Wed, 21 Oct 2026 07:28:00 GMT; HttpOnly',
    'bili_jct=token123; Path=/; Domain=.bilibili.com; Expires=Wed, 21 Oct 2026 07:28:00 GMT',
    'DedeUserID=393741907; Path=/',
    'buvid3=B3VALUE; Path=/',
])
jar = bili_login._extract_cookies(resp)
check('拿到 SESSDATA', 'SESSDATA' in jar, jar)
check('SESSDATA 值未被 Expires 逗号截断',
      jar.get('SESSDATA') == 'abc%2C123%2Cxyz', jar.get('SESSDATA'))
check('bili_jct / DedeUserID / buvid3 都在',
      all(k in jar for k in ('bili_jct', 'DedeUserID', 'buvid3')), jar)

print('[2] 兜底：raw 头为空时用 requests 的 cookie jar')
resp2 = FakeResp(set_cookies=[], cookies={'SESSDATA': 'from_jar'})
jar2 = bili_login._extract_cookies(resp2)
check('从 cookie jar 兜底取到', jar2.get('SESSDATA') == 'from_jar', jar2)

print('[3] Cookie 头拼接顺序')
header = bili_login.build_cookie_header({
    'buvid3': 'B3', 'SESSDATA': 'SESS', 'bili_jct': 'JCT', 'unknown': 'U'})
check('SESSDATA 在最前', header.startswith('SESSDATA=SESS'), header)
check('未知字段排最后', header.index('unknown=U') > header.index('bili_jct'), header)
check('空 jar 返回空串', bili_login.build_cookie_header({}) == '')

print('[4] 轮询状态映射')


def fake_get(payload):
    def _get(*args, **kwargs):
        return FakeResp(payload)
    return _get


real_get = bili_login.requests.get
real_verify = bili_login.verify
try:
    for code, expected in ((86101, 'waiting'), (86090, 'scanned'), (86038, 'expired')):
        bili_login.requests.get = fake_get({'data': {'code': code}})
        r = bili_login.poll('k')
        check(f'data.code={code} -> {expected}', r.get('state') == expected, r)

    bili_login.requests.get = fake_get({'data': {'code': 99999, 'message': '怪状态'}})
    r = bili_login.poll('k')
    check('未知状态码判为 failed', r.get('state') == 'failed', r)
    check('带上错误信息', bool(r.get('error')), r)

    print('[5] 登录成功但缺 SESSDATA -> 判失败')
    bili_login.requests.get = lambda *a, **k: FakeResp(
        {'data': {'code': 0}}, set_cookies=['bili_jct=x; Path=/'])
    r = bili_login.poll('k')
    check('无 SESSDATA 时 failed', r.get('state') == 'failed', r)
    check('提示重试', 'SESSDATA' in (r.get('error') or ''), r)

    print('[6] 登录成功且校验通过 -> success')
    bili_login.requests.get = lambda *a, **k: FakeResp(
        {'data': {'code': 0}},
        set_cookies=['SESSDATA=S%2C1%2C2; Path=/', 'bili_jct=T; Path=/'])
    bili_login.verify = lambda cookie, timeout=15: {'ok': True, 'login': True,
                                                    'uname': '测试账号', 'vip': ''}
    r = bili_login.poll('k')
    check('state=success', r.get('state') == 'success', r)
    check('带出账号名', r.get('uname') == '测试账号', r)
    check('带出 cookie', 'SESSDATA' in (r.get('cookie') or ''), r)

    print('[7] 校验不通过 -> failed')
    bili_login.verify = lambda cookie, timeout=15: {'ok': True, 'login': False,
                                                    'error': 'Cookie 无效'}
    r = bili_login.poll('k')
    check('校验失败时 failed', r.get('state') == 'failed', r)
finally:
    bili_login.requests.get = real_get
    bili_login.verify = real_verify

print('[8] 空 key 防御')
check('空 key 判 failed', bili_login.poll('').get('state') == 'failed')

print()
if failures:
    print(f'扫码登录自检失败 {len(failures)} 项: {", ".join(failures)}')
    sys.exit(1)
print('扫码登录自检通过')
