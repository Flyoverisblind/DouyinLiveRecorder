# -*- coding: utf-8 -*-

"""
从本机浏览器自动读取 B 站 Cookie，并写回 config.ini。

背景：B 站画质权限取决于 SESSDATA 是否有效，而未登录时只放行 qn=250（超清，
约 720p）。SESSDATA 没法用代码续期，只能来自一次真实登录；但**浏览器里登录过**
之后，Cookie 会一直存在浏览器里，于是可以定期把它同步到配置，避免录制悄悄降级。

支持：
* Chromium 系（Chrome / Edge / Brave …）：cookie 库是 SQLite + AES-GCM 加密
  （Windows 上用 DPAPI 保护主密钥，v10 前缀）。Chrome 正在运行时库也能读；
  部分浏览器（如 Edge）会用独占锁，此时需要先关掉浏览器。
* Firefox：cookies.sqlite 明文，直接读。
* 新版 Chrome 的 v20（App-Bound 加密）无法解密，会明确报出来而不是静默失败。

只读取 bilibili 相关 cookie，不会碰其它站点，也不会把数据发到本机以外。
"""

import base64
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

BILI_HOST_HINT = 'bilibili'
# B 站网页端需要的 cookie，按重要性排序
WANTED = ('SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'buvid3', 'buvid4',
          'bili_ticket', 'bili_ticket_expires', 'CURRENT_QUALITY', 'CURRENT_FNVAL')

_IS_WIN = os.name == 'nt'


# ---------------------------------------------------------------- Windows 工具

def _copy_locked_file(src: str, dst: str) -> bool:
    """用共享模式打开并复制（Chromium 运行时会给 cookie 库加锁）。"""
    if not _IS_WIN:
        try:
            shutil.copy2(src, dst)
            return True
        except OSError:
            return False
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.restype = ctypes.c_void_p
    k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                wt.DWORD, wt.DWORD, ctypes.c_void_p]
    k32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD,
                             ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]

    handle = k32.CreateFileW(src, 0x80000000, 0x7, None, 3, 0x80, None)
    if not handle or handle == ctypes.c_void_p(-1).value:
        return False
    try:
        buf = ctypes.create_string_buffer(1 << 20)
        total = 0
        with open(dst, 'wb') as out:
            while True:
                read = wt.DWORD(0)
                if not k32.ReadFile(handle, buf, len(buf), ctypes.byref(read), None) \
                        or read.value == 0:
                    break
                out.write(buf.raw[:read.value])
                total += read.value
        return total > 0
    finally:
        k32.CloseHandle(handle)


def _dpapi_unprotect(blob: bytes) -> bytes:
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wt.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(blob, len(blob))
    blob_in = DATA_BLOB(len(blob), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError('DPAPI 解密失败')
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _chromium_key(user_data: str) -> bytes:
    state = os.path.join(user_data, 'Local State')
    data = json.load(open(state, encoding='utf-8'))
    enc = base64.b64decode(data['os_crypt']['encrypted_key'])
    return _dpapi_unprotect(enc[5:])          # 去掉 b'DPAPI' 前缀


def _decrypt_v10(value: bytes, key: bytes) -> str:
    from Crypto.Cipher import AES      # pycryptodome
    nonce, payload = value[3:15], value[15:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(payload[:-16], payload[-16:]).decode('utf-8', 'replace')


# ---------------------------------------------------------------- 各浏览器

def chromium_candidates() -> list:
    local = os.environ.get('LOCALAPPDATA', '')
    appdata = os.environ.get('APPDATA', '')
    roots = {
        'Chrome': os.path.join(local, 'Google', 'Chrome', 'User Data'),
        'Edge': os.path.join(local, 'Microsoft', 'Edge', 'User Data'),
        'Brave': os.path.join(local, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'Vivaldi': os.path.join(local, 'Vivaldi', 'User Data'),
        '360Chrome': os.path.join(local, '360Chrome', 'Chrome', 'User Data'),
        'QQBrowser': os.path.join(local, 'Tencent', 'QQBrowser', 'User Data'),
        'Opera': os.path.join(appdata, 'Opera Software', 'Opera Stable'),
    }
    result = []
    for name, root in roots.items():
        if not os.path.isdir(root):
            continue
        if name == 'Opera':
            profiles = [''] if os.path.exists(os.path.join(root, 'Network', 'Cookies')) else []
        else:
            profiles = [p for p in os.listdir(root)
                        if os.path.isdir(os.path.join(root, p))]
        for profile in profiles:
            base = os.path.join(root, profile) if profile else root
            for rel in (('Network', 'Cookies'), ('Cookies',)):
                db = os.path.join(base, *rel)
                if os.path.exists(db):
                    result.append((name, root, profile, db))
                    break
    return result


def firefox_candidates() -> list:
    appdata = os.environ.get('APPDATA', '')
    result = []
    for profile in glob.glob(os.path.join(appdata, 'Mozilla', 'Firefox', 'Profiles', '*')):
        db = os.path.join(profile, 'cookies.sqlite')
        if os.path.exists(db):
            result.append((os.path.basename(profile), db))
    return result


def read_chromium(db_path: str, user_data: str) -> dict:
    """返回 {'cookies': {name: value}, 'error': str, 'locked': bool}"""
    tmp = tempfile.mktemp(suffix='.sqlite')
    try:
        if not _copy_locked_file(db_path, tmp):
            return {'cookies': {}, 'locked': True,
                    'error': '数据库被浏览器独占锁定，请先关闭该浏览器'}
        con = sqlite3.connect(tmp)
        try:
            rows = con.execute(
                "SELECT host_key, name, encrypted_value, value FROM cookies "
                "WHERE host_key LIKE ?", (f'%{BILI_HOST_HINT}%',)).fetchall()
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        return {'cookies': {}, 'error': f'读取失败: {exc}'}
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    if not rows:
        return {'cookies': {}, 'error': ''}

    try:
        key = _chromium_key(user_data)
    except Exception as exc:  # noqa: BLE001
        return {'cookies': {}, 'error': f'取主密钥失败: {exc}'}

    cookies = {}
    unsupported = 0
    for _host, name, enc, plain in rows:
        if plain:
            cookies[name] = plain
            continue
        if not enc:
            continue
        prefix = bytes(enc[:3])
        if prefix == b'v10':
            try:
                cookies[name] = _decrypt_v10(enc, key)
            except Exception:  # noqa: BLE001
                pass
        else:
            unsupported += 1        # v20 = 新版 App-Bound 加密
    if not cookies and unsupported:
        return {'cookies': {}, 'error': f'{unsupported} 条 cookie 使用了 v20（App-Bound）加密，'
                                        f'本功能无法解密；请改用 Chrome 或 Firefox 登录'}
    return {'cookies': cookies, 'error': ''}


def read_firefox(db_path: str) -> dict:
    tmp = tempfile.mktemp(suffix='.sqlite')
    try:
        shutil.copy2(db_path, tmp)
        con = sqlite3.connect(tmp)
        try:
            rows = con.execute(
                "SELECT name, value FROM moz_cookies WHERE host LIKE ?",
                (f'%{BILI_HOST_HINT}%',)).fetchall()
        finally:
            con.close()
        return {'cookies': {name: value for name, value in rows}, 'error': ''}
    except Exception as exc:  # noqa: BLE001
        return {'cookies': {}, 'error': f'读取失败: {exc}'}
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def build_cookie_header(cookies: dict) -> str:
    """按固定顺序拼 Cookie 请求头，便于 diff 与去重。"""
    ordered = [f'{name}={cookies[name]}' for name in WANTED if name in cookies]
    extras = [f'{name}={value}' for name, value in cookies.items() if name not in WANTED]
    return '; '.join(ordered + extras)


def read_bilibili_cookie(browser: str = 'auto') -> dict:
    """尝试所有浏览器，返回第一个拿到 SESSDATA 的结果。

    返回 {'ok', 'cookie', 'source', 'error', 'attempts': [...]}
    """
    attempts = []
    targets = []
    if browser in ('auto', 'chromium'):
        for name, root, profile, db in chromium_candidates():
            targets.append(('chromium', f'{name}/{profile}', db, root))
    if browser in ('auto', 'firefox'):
        for name, db in firefox_candidates():
            targets.append(('firefox', f'Firefox/{name}', db, ''))

    for kind, label, db, root in targets:
        if kind == 'chromium':
            info = read_chromium(db, root)
        else:
            info = read_firefox(db)
        cookies = info.get('cookies') or {}
        has_sess = 'SESSDATA' in cookies and cookies['SESSDATA']
        attempts.append({'source': label, 'count': len(cookies),
                         'has_sessdata': has_sess, 'error': info.get('error', ''),
                         'locked': info.get('locked', False)})
        if has_sess:
            return {'ok': True, 'cookie': build_cookie_header(cookies),
                    'source': label, 'error': '', 'attempts': attempts}

    error = '没有在任何浏览器里找到已登录的 B 站 Cookie'
    locked = [a['source'] for a in attempts if a.get('locked')]
    if locked:
        error += f'（{", ".join(locked)} 被浏览器锁定，请关闭后重试）'
    return {'ok': False, 'cookie': '', 'source': '', 'error': error, 'attempts': attempts}


# ---------------------------------------------------------------- 校验与写回

def verify_cookie(cookie: str, timeout: int = 15) -> dict:
    """调 B 站 nav 接口确认登录态。返回 {'ok', 'login', 'uname', 'vip'}。"""
    import urllib.request
    if not cookie:
        return {'ok': False, 'login': False, 'error': 'Cookie 为空'}
    req = urllib.request.Request(
        'https://api.bilibili.com/x/web-interface/nav',
        headers={'User-Agent': 'Mozilla/5.0', 'Cookie': cookie,
                 'referer': 'https://www.bilibili.com/'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'login': False, 'error': f'请求失败: {exc}'}
    if data.get('code') == -101:
        return {'ok': True, 'login': False, 'error': 'Cookie 已失效（未登录）'}
    payload = data.get('data') or {}
    return {'ok': True, 'login': bool(payload.get('isLogin')),
            'uname': payload.get('uname', ''),
            'vip': (payload.get('vip_label') or {}).get('text', ''),
            'error': ''}


def write_cookie_to_config(config_path: str, cookie: str) -> dict:
    """把 B站cookie 写回 config.ini（尽量走控制台的无损写入，保住注释）。"""
    if not os.path.isfile(config_path):
        return {'ok': False, 'error': f'配置文件不存在: {config_path}'}
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web')
    web_dir = os.path.normpath(web_dir)
    try:
        if web_dir not in sys.path:
            sys.path.insert(0, web_dir)
        import config_store
        result = config_store.update_config_file(config_path, {'Cookie': {'B站cookie': cookie}})
        return {'ok': True, 'changed': result.get('changed', [])}
    except Exception as exc:  # noqa: BLE001 - 退回文本替换
        try:
            with open(config_path, 'r', encoding='utf-8-sig') as fp:
                lines = fp.readlines()
            hit = False
            for index, line in enumerate(lines):
                if line.strip().lower().startswith('b站cookie'):
                    lines[index] = f'B站cookie = {cookie}\n'
                    hit = True
                    break
            if not hit:
                return {'ok': False, 'error': f'写入失败（{exc}），且文件里没有 B站cookie 这一行'}
            with open(config_path, 'w', encoding='utf-8-sig') as fp:
                fp.writelines(lines)
            return {'ok': True, 'changed': ['Cookie.B站cookie']}
        except OSError as write_exc:
            return {'ok': False, 'error': f'写入失败: {write_exc}'}


def sync(project_root: str = None, browser: str = 'auto', write: bool = True) -> dict:
    """读取 → 校验 → （可选）写回。返回一份可打印的结果。"""
    root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root, 'config', 'config.ini')
    read = read_bilibili_cookie(browser)
    result = {'ok': False, 'source': read.get('source', ''),
              'attempts': read.get('attempts', [])}
    if not read.get('ok'):
        result['error'] = read.get('error', '读取失败')
        return result
    check = verify_cookie(read['cookie'])
    result['login'] = check.get('login')
    result['uname'] = check.get('uname', '')
    result['vip'] = check.get('vip', '')
    if not check.get('login'):
        result['error'] = check.get('error') or '浏览器里的 Cookie 也已失效，请重新登录'
        return result
    if write:
        written = write_cookie_to_config(config_path, read['cookie'])
        if not written.get('ok'):
            result['error'] = written.get('error', '写入配置失败')
            return result
        result['written'] = written.get('changed', [])
    result['ok'] = True
    return result


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='从本机浏览器同步 B 站 Cookie')
    parser.add_argument('--browser', default='auto', choices=['auto', 'chromium', 'firefox'])
    parser.add_argument('--no-write', action='store_true', help='只检查，不写回配置')
    parser.add_argument('--project-root', default='')
    args = parser.parse_args(argv)

    result = sync(args.project_root or None, args.browser, write=not args.no_write)
    for attempt in result.get('attempts', []):
        flag = 'SESSDATA' if attempt.get('has_sessdata') else f'{attempt.get("count", 0)} 条'
        extra = f'  ← {attempt["error"]}' if attempt.get('error') else ''
        print(f'  [{attempt["source"]}] {flag}{extra}')
    if result.get('ok'):
        print(f'\n同步成功：来源 {result["source"]}，账号 {result.get("uname")}'
              f'{("（" + result["vip"] + "）") if result.get("vip") else ""}')
        if result.get('written'):
            print(f'已写入配置：{", ".join(result["written"])}')
        return 0
    print(f'\n同步失败：{result.get("error")}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
