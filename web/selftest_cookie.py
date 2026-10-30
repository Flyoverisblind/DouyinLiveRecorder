# -*- coding: utf-8 -*-
"""
Cookie 同步模块自检（不访问网络、不修改真实配置）。

用法： python web/selftest_cookie.py
"""
import os
import shutil
import sys
import tempfile

WEB = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB)
for path in (WEB, PROJECT_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

from src import cookie_source  # noqa: E402

# 所有写入都指向临时副本，绝不碰真实配置（曾把测试值写进真实 config.ini）
tmp_root = tempfile.mkdtemp(prefix='cookie_test_')
os.makedirs(os.path.join(tmp_root, 'config'), exist_ok=True)
shutil.copyfile(os.path.join(PROJECT_ROOT, 'config', 'config.ini'),
                os.path.join(tmp_root, 'config', 'config.ini'))

failures = []


def check(name, ok, detail=''):
    mark = 'OK  ' if ok else 'FAIL'
    print(f'  [{mark}] {name}{("  -> " + str(detail)) if detail and not ok else ""}')
    if not ok:
        failures.append(name)


print('[1] Cookie 头拼接')
cookies = {'buvid3': 'B3', 'SESSDATA': 'SESS', 'bili_jct': 'JCT', 'zzz': 'Z'}
header = cookie_source.build_cookie_header(cookies)
check('SESSDATA 在最靠前的已知字段里', header.startswith('SESSDATA=SESS'), header)
check('已知字段按固定顺序', header.index('SESSDATA') < header.index('bili_jct')
      < header.index('buvid3'), header)
check('未知字段排在后面', header.index('zzz') > header.index('buvid3'), header)
check('空字典返回空串', cookie_source.build_cookie_header({}) == '')
single = cookie_source.build_cookie_header({'SESSDATA': 'only'})
check('单字段不带多余分隔符', single == 'SESSDATA=only', single)

print('[2] 缺 SESSDATA 时不应认为成功')
real_read = cookie_source.read_bilibili_cookie
try:
    cookie_source.read_bilibili_cookie = lambda browser='auto': {
        'ok': False, 'cookie': '', 'source': '',
        'error': '没有在任何浏览器里找到已登录的 B 站 Cookie', 'attempts': []}
    result = cookie_source.sync(tmp_root, 'auto', write=False)
    check('sync 返回 ok=False', result['ok'] is False)
    check('sync 带出错误信息', bool(result.get('error')))
finally:
    cookie_source.read_bilibili_cookie = real_read

print('[3] 读到 Cookie 但校验不通过时不应写配置')
written = {'called': False}


def fake_write(*_args, **_kwargs):
    written['called'] = True
    return {'ok': True, 'changed': ['Cookie.B站cookie']}


real_verify = cookie_source.verify_cookie
real_write = cookie_source.write_cookie_to_config
try:
    cookie_source.read_bilibili_cookie = lambda browser='auto': {
        'ok': True, 'cookie': 'SESSDATA=expired', 'source': 'Chrome/Default',
        'error': '', 'attempts': []}
    cookie_source.verify_cookie = lambda cookie, timeout=15: {
        'ok': True, 'login': False, 'error': 'Cookie 已失效（未登录）'}
    cookie_source.write_cookie_to_config = fake_write
    result = cookie_source.sync(tmp_root, 'auto', write=True)
    check('未登录时 sync 失败', result['ok'] is False)
    check('未登录时不写配置', written['called'] is False)
finally:
    cookie_source.read_bilibili_cookie = real_read
    cookie_source.verify_cookie = real_verify
    cookie_source.write_cookie_to_config = real_write

print('[4] 校验通过时应写配置并报告来源')
try:
    cookie_source.read_bilibili_cookie = lambda browser='auto': {
        'ok': True, 'cookie': 'SESSDATA=good', 'source': 'Chrome/Default',
        'error': '', 'attempts': []}
    cookie_source.verify_cookie = lambda cookie, timeout=15: {
        'ok': True, 'login': True, 'uname': '测试账号', 'vip': '', 'error': ''}
    result = cookie_source.sync(tmp_root, 'auto', write=True)
    check('登录态有效时 sync 成功', result['ok'] is True, result)
    check('带出账号名', result.get('uname') == '测试账号', result)
    check('报告来源', result.get('source') == 'Chrome/Default', result)
finally:
    cookie_source.read_bilibili_cookie = real_read
    cookie_source.verify_cookie = real_verify
    cookie_source.write_cookie_to_config = real_write

print('[5] 校验接口对空 Cookie 的防御')
check('空 Cookie 直接判失败', cookie_source.verify_cookie('')['login'] is False)

print('[6] 写配置：不存在的文件要报错而不是崩')
result = cookie_source.write_cookie_to_config(
    os.path.join(tempfile.gettempdir(), 'no_such_config_xyz.ini'), 'a=b')
check('文件不存在时 ok=False', result['ok'] is False, result)
check('给出错误信息', bool(result.get('error')), result)

print()
shutil.rmtree(tmp_root, ignore_errors=True)
if failures:
    print(f'Cookie 模块自检失败 {len(failures)} 项: {", ".join(failures)}')
    sys.exit(1)
print('Cookie 模块自检通过')
