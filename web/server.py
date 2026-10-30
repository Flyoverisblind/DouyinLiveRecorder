# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 本地 Web 服务

只使用 Python 标准库（http.server），不需要安装 Flask/FastAPI 等额外依赖。

启动：
    python web/server.py                 # 默认 http://127.0.0.1:8765
    python web/server.py --port 9000 --open
"""

import argparse
import json
import mimetypes
import os
import queue
import re
import socket
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)

import config_store          # noqa: E402
import files_api             # noqa: E402
import media_jobs            # noqa: E402
import media_tools           # noqa: E402
import paths                 # noqa: E402
from process_manager import EnvironmentProbe, RecorderProcess  # noqa: E402
import schema as schema_mod  # noqa: E402

STATIC_DIR = os.path.join(WEB_DIR, 'static')
MIME_OVERRIDES = {
    '.js': 'application/javascript; charset=utf-8',
    '.mjs': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
    '.map': 'application/json; charset=utf-8',
}


def json_default(obj):
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, extra: dict = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra or {}


class WebConsole:
    """应用状态与业务逻辑。"""

    def __init__(self, project_root: str, python_exe: str, host: str = '127.0.0.1', port: int = 8765):
        self.project_root = os.path.abspath(project_root)
        self.python_exe = python_exe
        self.host = host
        self.port = port
        self.started_at = time.time()
        self.config_file = os.path.join(self.project_root, paths.CONFIG_REL)
        self.url_file = os.path.join(self.project_root, paths.URL_CONFIG_REL)
        self.log_dir = os.path.join(self.project_root, paths.LOG_DIR_REL)
        self.recorder = RecorderProcess(self.project_root, python_exe)
        self.probe = EnvironmentProbe(self.project_root, python_exe)
        # 合并 / 裁切这类后处理在后台串行执行，避免长任务把请求卡死
        self.media_jobs = media_jobs.MediaJobManager(self.project_root)
        self.version = self._read_version()
        # 只监听本机时，进一步拒绝非本机 Host 的请求（DNS rebinding 防护）
        self.enforce_local_host = host in ('127.0.0.1', 'localhost', '::1')
        self._stop_event = threading.Event()

    # ------------------------------------------------------------ 基础信息
    def _read_version(self) -> str:
        try:
            with open(os.path.join(self.project_root, 'main.py'), 'r', encoding='utf-8', errors='ignore') as fp:
                head = fp.read(4000)
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', head, re.MULTILINE)
            if match:
                return match.group(1)
        except OSError:
            pass
        return 'unknown'

    def ensure_config(self) -> None:
        """config.ini 不存在时按 schema 生成一份默认配置。"""
        if os.path.isfile(self.config_file):
            return
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        updates = {}
        for section_name, fields in schema_mod.FIELDS.items():
            updates[section_name] = {}
            for key, meta in fields.items():
                value = meta.get('default', '')
                if isinstance(value, bool):
                    value = '是' if value else '否'
                updates[section_name][key] = value
        config_store.update_config_file(self.config_file, updates)

    def ensure_url_file(self) -> None:
        if not os.path.isfile(self.url_file):
            os.makedirs(os.path.dirname(self.url_file), exist_ok=True)
            config_store.write_url_lines(self.url_file, [])

    def ensure_schema_keys(self) -> None:
        """把 schema 里登记、但 config.ini 里还不存在的键补上默认值。

        上游 main.py 遇到缺失的键会用 configparser 重写整个文件（注释就没了），
        控制台先按 schema 补齐，既保住注释，也能让新功能立刻出现在配置页上。

        两个坑必须处理：
        1. configparser 的键名**大小写不敏感**，而 schema 里可能写 `SMTP邮件服务器`、
           文件里却是 `smtp邮件服务器`（main.py 用 configparser 写入时会小写）。
           所以比较必须 casefold，否则会加出重复键，让 main.py 抛
           DuplicateOptionError 直接起不来。
        2. 历史遗留的重复键会直接把 main.py 打死，启动时顺手清一次。
        """
        if not os.path.isfile(self.config_file):
            return
        try:
            config_store.dedupe_keys(self.config_file)
        except Exception:
            pass
        try:
            existing = config_store.read_config_values(self.config_file)
        except Exception:
            return
        updates = schema_mod.missing_keys(existing)
        if not updates:
            return
        try:
            config_store.update_config_file(self.config_file, updates)
        except Exception:
            pass

    def ensure_dirs(self) -> None:
        """与 main.py 行为一致：提前建好保存目录与日志目录，保证文件页可用。"""
        for target in (paths.default_save_path(self.project_root),
                       paths.resolve_save_path(self.project_root)[0],
                       self.log_dir):
            try:
                if target:
                    os.makedirs(target, exist_ok=True)
            except OSError:
                pass

    def save_roots(self) -> list:
        save_path, _source = paths.resolve_save_path(self.project_root)
        return files_api.allowed_roots(self.project_root, save_path)

    # ------------------------------------------------------------ 状态
    def state(self) -> dict:
        self.ensure_config()
        self.ensure_url_file()
        save_path, save_source = paths.resolve_save_path(self.project_root)
        try:
            urls = config_store.read_url_file(self.url_file)
            url_stats = {
                'total': len(urls),
                'enabled': sum(1 for item in urls if item.enabled),
                'disabled': sum(1 for item in urls if not item.enabled),
                'invalid': sum(1 for item in urls if not item.valid),
            }
        except Exception as exc:
            url_stats = {'total': 0, 'enabled': 0, 'disabled': 0, 'invalid': 0, 'error': str(exc)}

        return {
            'app': {
                'version': self.version,
                'project_root': self.project_root,
                'python': self.python_exe,
                'host': self.host,
                'port': self.port,
                'started_at': self.started_at,
                'server_time': time.time(),
                'config_file': self.config_file,
                'url_file': self.url_file,
                'platform': sys.platform,
            },
            'process': self.recorder.status(),
            'env': self.probe.get(),
            'urls': url_stats,
            'save_path': save_path,
            'save_path_source': save_source,
        }

    # ------------------------------------------------------------ 配置
    def get_config(self) -> dict:
        self.ensure_config()
        values = config_store.read_config_values(self.config_file)
        return {'sections': schema_mod.build_schema(values)}

    def update_config(self, updates: dict) -> dict:
        if not isinstance(updates, dict) or not updates:
            raise ApiError('请求内容为空')
        values = config_store.read_config_values(self.config_file)
        known_sections = set(values.keys()) | set(schema_mod.FIELDS.keys()) | \
            {item['name'] for item in schema_mod.SECTIONS}
        cleaned, errors = {}, []
        for section, items in updates.items():
            if not isinstance(items, dict):
                continue
            if section not in known_sections:
                errors.append({'section': section, 'key': '', 'error': f'未知的配置分组: {section}'})
                continue
            registered = schema_mod.FIELDS.get(section, {})
            existing = values.get(section, {})
            for key, raw in items.items():
                # 只允许写「文件里已有的键」或「schema 已登记的键」，
                # 避免客户端把拼写错误的键写进配置文件。
                if key not in existing and key not in registered:
                    errors.append({'section': section, 'key': key, 'error': f'未知的配置项: {key}'})
                    continue
                meta = schema_mod.field_meta(section, key, existing.get(key, ''))
                try:
                    cleaned.setdefault(section, {})[key] = self._coerce(meta, raw)
                except ValueError as exc:
                    errors.append({'section': section, 'key': key, 'error': str(exc)})
        if errors:
            raise ApiError('部分参数不合法，未保存', extra={'errors': errors})
        if not cleaned:
            return {'ok': True, 'changed': [], 'message': '没有需要保存的改动'}

        result = config_store.update_config_file(self.config_file, cleaned)
        # 保存后如果设置了保存路径，尝试自动创建目录
        save_path, source = paths.resolve_save_path(self.project_root)
        created = False
        if source == 'config' and save_path:
            try:
                if not os.path.isdir(save_path):
                    os.makedirs(save_path, exist_ok=True)
                    created = True
            except OSError:
                created = False
        result['save_path'] = save_path
        result['save_path_created'] = created
        return result

    @staticmethod
    def _coerce(meta: dict, raw) -> str:
        ftype = meta.get('type', 'text')
        if ftype == 'bool':
            if isinstance(raw, bool):
                return '是' if raw else '否'
            text = str(raw).strip()
            if text in ('是', '否'):
                return text
            if text.lower() in ('true', '1', 'yes', 'on'):
                return '是'
            if text.lower() in ('false', '0', 'no', 'off', ''):
                return '否'
            raise ValueError(f'布尔值只能是「是」或「否」，收到: {raw}')
        if ftype == 'int':
            text = str(raw).strip()
            if text == '':
                return ''
            if not re.fullmatch(r'-?\d+', text):
                raise ValueError(f'需要整数，收到: {raw}')
            value = int(text)
            if meta.get('min') is not None and value < meta['min']:
                raise ValueError(f'不能小于 {meta["min"]}')
            if meta.get('max') is not None and value > meta['max']:
                raise ValueError(f'不能大于 {meta["max"]}')
            return str(value)
        if ftype == 'float':
            text = str(raw).strip()
            if text == '':
                return ''
            try:
                value = float(text)
            except ValueError:
                raise ValueError(f'需要数字，收到: {raw}') from None
            if meta.get('min') is not None and value < meta['min']:
                raise ValueError(f'不能小于 {meta["min"]}')
            if meta.get('max') is not None and value > meta['max']:
                raise ValueError(f'不能大于 {meta["max"]}')
            return str(value)
        if ftype in ('select',) and meta.get('options'):
            text = str(raw).strip()
            if text and text not in meta['options']:
                raise ValueError(f'只能是 {"/".join(meta["options"])} 之一，收到: {text}')
            return text
        if ftype == 'multiselect' and meta.get('options'):
            if isinstance(raw, (list, tuple)):
                picked = [str(item).strip() for item in raw if str(item).strip()]
            else:
                picked = [item.strip() for item in re.split(r'[,，]', str(raw)) if item.strip()]
            invalid = [item for item in picked if item not in meta['options']]
            if invalid:
                raise ValueError(f'不支持的渠道: {", ".join(invalid)}')
            return ', '.join(picked)
        if ftype == 'list':
            if isinstance(raw, (list, tuple)):
                items = [str(item).strip() for item in raw]
            else:
                items = [item.strip() for item in re.split(r'[,，]', str(raw))]
            return ', '.join(item for item in items if item)
        return config_store.sanitize_value(raw)

    # ------------------------------------------------------------ URL 列表
    def get_urls(self) -> dict:
        self.ensure_url_file()
        entries = config_store.read_url_file(self.url_file)
        return {
            'items': [item.to_dict() for item in entries],
            'total': len(entries),
            'enabled': sum(1 for item in entries if item.enabled),
            'disabled': sum(1 for item in entries if not item.enabled),
        }

    def add_url(self, url: str, quality: str = '', name: str = '', enabled: bool = True) -> dict:
        url = (url or '').strip()
        if not url:
            raise ApiError('请填写直播间地址')
        entry = config_store.UrlEntry(-1, url)
        if not entry.valid:
            raise ApiError('这看起来不是一个有效的直播间地址')
        lines = config_store.read_url_lines(self.url_file)
        existing = {item.url for item in config_store.read_url_file(self.url_file)}
        if entry.url in existing:
            raise ApiError('该地址已在列表中')
        new_entry = config_store.UrlEntry(-1, url)
        new_entry.quality = (quality or '').strip()
        new_entry.name = (name or '').strip()
        new_entry.enabled = bool(enabled)
        lines.append(new_entry.to_line())
        config_store.write_url_lines(self.url_file, lines)
        return {'ok': True, 'line': new_entry.to_line(), **self.get_urls()}

    def update_url(self, index: int, url: str = None, quality: str = None,
                   name: str = None, enabled: bool = None) -> dict:
        lines = config_store.read_url_lines(self.url_file)
        if index < 0 or index >= len(lines):
            raise ApiError('找不到该条直播间记录，请刷新后重试')
        entry = config_store.UrlEntry(index, lines[index])
        if url is not None:
            entry.url = url.strip()
        if quality is not None:
            entry.quality = quality.strip()
        if name is not None:
            entry.name = name.strip()
        if enabled is not None:
            entry.enabled = bool(enabled)
        if not entry.url:
            raise ApiError('地址不能为空')
        lines[index] = entry.to_line()
        config_store.write_url_lines(self.url_file, lines)
        return {'ok': True, 'line': entry.to_line(), **self.get_urls()}

    def delete_urls(self, indexes: list) -> dict:
        lines = config_store.read_url_lines(self.url_file)
        targets = sorted({int(i) for i in indexes if 0 <= int(i) < len(lines)}, reverse=True)
        if not targets:
            raise ApiError('没有可删除的条目')
        for index in targets:
            lines.pop(index)
        config_store.write_url_lines(self.url_file, lines)
        return {'ok': True, 'removed': len(targets), **self.get_urls()}

    def toggle_urls(self, indexes: list, enabled: bool) -> dict:
        lines = config_store.read_url_lines(self.url_file)
        changed = 0
        for index in {int(i) for i in indexes if 0 <= int(i) < len(lines)}:
            entry = config_store.UrlEntry(index, lines[index])
            if entry.enabled != bool(enabled):
                entry.enabled = bool(enabled)
                lines[index] = entry.to_line()
                changed += 1
        config_store.write_url_lines(self.url_file, lines)
        return {'ok': True, 'changed': changed, **self.get_urls()}

    def import_urls(self, text: str, mode: str = 'append') -> dict:
        raw_lines = [] if mode == 'replace' else config_store.read_url_lines(self.url_file)
        existing = {item.url for item in config_store.read_url_file(self.url_file)}
        added, skipped = 0, 0
        for line in (text or '').splitlines():
            line = line.strip()
            if not line:
                continue
            entry = config_store.UrlEntry(-1, line)
            if not entry.valid:
                skipped += 1
                continue
            if entry.url in existing:
                skipped += 1
                continue
            existing.add(entry.url)
            raw_lines.append(entry.to_line())
            added += 1
        config_store.write_url_lines(self.url_file, raw_lines)
        return {'ok': True, 'added': added, 'skipped': skipped, **self.get_urls()}

    # ------------------------------------------------------------ 控制
    def control_start(self, force: bool = False) -> dict:
        urls = config_store.read_url_file(self.url_file)
        enabled = [item for item in urls if item.enabled]
        if not enabled:
            raise ApiError('还没有启用的直播间地址，请先在「直播间地址」里添加', status=400)
        env = self.probe.get(force=True)
        if not force:
            if not env['dependencies']['ok']:
                missing = ', '.join(env['dependencies'].get('missing', []))
                raise ApiError(
                    f'当前 Python 缺少依赖包: {missing}。请先执行 '
                    f'pip install -r requirements.txt（或使用项目内的 .venv）',
                    status=400, extra={'missing': env['dependencies'].get('missing', [])})
            if not env['ffmpeg']['ok']:
                raise ApiError('未检测到 ffmpeg，无法录制。请先安装 ffmpeg 或放入项目的 ffmpeg 目录', status=400)
        result = self.recorder.start()
        if not result.get('ok'):
            raise ApiError(result.get('error', '启动失败'))
        return result

    def control_stop(self) -> dict:
        return self.recorder.stop()

    def sync_cookie(self) -> dict:
        """从本机浏览器读取 B 站 Cookie，校验通过后写回 config.ini。"""
        root = self.project_root
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            from src import cookie_source
        except Exception as exc:  # noqa: BLE001
            return {'ok': False, 'error': f'无法加载 cookie_source: {exc}'}
        result = cookie_source.sync(root, 'auto', write=True)
        if result.get('ok'):
            result['hint'] = '下次录制（或点「重启」）后生效'
        return result

    def control_restart(self) -> dict:
        env = self.probe.get(force=True)
        if not env['dependencies']['ok']:
            missing = ', '.join(env['dependencies'].get('missing', []))
            raise ApiError(f'当前 Python 缺少依赖包: {missing}', status=400)
        return self.recorder.restart()

    # ------------------------------------------------------------ 日志文件
    def log_files(self) -> list:
        if not os.path.isdir(self.log_dir):
            return []
        items = []
        for name in sorted(os.listdir(self.log_dir)):
            full = os.path.join(self.log_dir, name)
            if not os.path.isfile(full):
                continue
            stat = os.stat(full)
            items.append({
                'name': name,
                'size': stat.st_size,
                'size_text': files_api.human_size(stat.st_size),
                'mtime': stat.st_mtime,
                'mtime_text': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
            })
        items.sort(key=lambda item: item['mtime'], reverse=True)
        return items

    def tail_log(self, name: str, lines: int = 300) -> dict:
        safe_name = os.path.basename(name or '')
        if not safe_name:
            raise ApiError('缺少日志文件名')
        full = os.path.join(self.log_dir, safe_name)
        if not os.path.isfile(full):
            raise ApiError(f'日志文件不存在: {safe_name}', status=404)
        lines = max(1, min(int(lines or 300), 5000))
        with open(full, 'r', encoding='utf-8', errors='replace') as fp:
            data = fp.readlines()
        return {
            'name': safe_name,
            'lines': [line.rstrip('\n') for line in data[-lines:]],
            'total_lines': len(data),
        }


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = 'DLR-WebConsole/1.0'
    protocol_version = 'HTTP/1.1'

    app: WebConsole = None
    token: str = ''

    # ------------------------------------------------------------ 工具
    def log_message(self, fmt, *args):  # 保持控制台干净
        if os.environ.get('DLR_WEB_DEBUG'):
            sys.stderr.write('[web] %s - %s\n' % (self.address_string(), fmt % args))

    def _json(self, payload, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False, default=json_default).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message, status: int = 400, extra: dict = None):
        payload = {'ok': False, 'error': message}
        if extra:
            payload.update(extra)
        self._json(payload, status)

    def _read_body(self) -> dict:
        content_type = (self.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type and content_type != 'application/json':
            # 只接受 JSON：跨站表单（text/plain 等）无法伪造出合法 JSON 请求
            raise ApiError('请求需要使用 application/json 提交', status=415)
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0:
            return {}
        if length > 32 * 1024 * 1024:
            raise ApiError('请求体过大', status=413)
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(f'请求内容不是合法的 JSON: {exc}') from exc

    def _check_origin(self) -> None:
        """阻止其它网站的页面在后台操作本控制台（CSRF）。"""
        origin = self.headers.get('Origin')
        if not origin:
            return
        host = self.headers.get('Host') or ''
        try:
            parsed = urlparse(origin)
        except ValueError:
            raise ApiError('来源非法', status=403) from None
        if parsed.netloc and parsed.netloc != host:
            raise ApiError('跨站请求已被拒绝', status=403)

    def _check_host(self) -> None:
        """仅监听本机时，拒绝用非本机域名访问（防止 DNS rebinding）。"""
        if not getattr(self.app, 'enforce_local_host', False):
            return
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]').lower()
        if host not in ('127.0.0.1', 'localhost', '::1', ''):
            raise ApiError('仅允许通过本机地址访问', status=403)

    def _check_token(self, query: dict) -> None:
        if not self.token:
            return
        supplied = self.headers.get('X-DLR-Token') or (query.get('token', [''])[0])
        if supplied != self.token:
            raise ApiError('访问令牌不正确', status=401)

    # ------------------------------------------------------------ 路由
    def do_GET(self):
        self._dispatch('GET')

    def do_POST(self):
        self._dispatch('POST')

    def do_PUT(self):
        self._dispatch('PUT')

    def do_DELETE(self):
        self._dispatch('DELETE')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Allow', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _dispatch(self, method: str):
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        query = parse_qs(parsed.query)
        # 每个请求在这里就把 body 读干净。放在 _handle_api 里不够早：
        # 有些接口（/api/control/stop、/api/logs/clear）根本不碰 body，
        # 残留字节会留在 keep-alive 连接里污染下一个请求
        # ——实测会变成 `{}GET /api/ping` 这种 501 Unsupported method。
        self._pending_body = None
        try:
            self._check_host()
            self._check_origin()
            self._check_token(query)
            if method in ('POST', 'PUT', 'DELETE'):
                self._pending_body = self._read_body()
            if route.startswith('/api/'):
                self._handle_api(method, route, query)
            elif method == 'GET':
                self._serve_static(route)
            else:
                self._error('不支持的请求方法', 405)
        except ApiError as exc:
            self._error(exc.message, exc.status, exc.extra)
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass
        except Exception as exc:  # noqa: BLE001 - 兜底，避免单个请求打死服务
            traceback.print_exc()
            self._error(f'服务器内部错误: {exc}', 500)

    def _handle_api(self, method: str, route: str, query: dict):
        app = self.app
        # body 已在 _dispatch 里读好，这里直接复用，避免二次读取或残留
        body_cache = {'value': self._pending_body if self._pending_body is not None else {}}

        def body() -> dict:
            return body_cache['value']

        def arg(name, default=None, cast=None):
            if name in query:
                value = query[name][0]
            elif name in body():
                value = body()[name]
            else:
                return default
            if cast and value is not None:
                try:
                    return cast(value)
                except (TypeError, ValueError):
                    raise ApiError(f'参数 {name} 格式不正确: {value}') from None
            return value

        # ---------------- 基础
        if route == '/api/ping' and method == 'GET':
            return self._json({'ok': True, 'time': time.time(), 'version': app.version})

        if route == '/api/state' and method == 'GET':
            return self._json({'ok': True, **app.state()})

        # ---------------- 配置
        if route == '/api/config' and method == 'GET':
            return self._json({'ok': True, **app.get_config()})

        if route == '/api/config' and method == 'POST':
            payload = body()
            updates = payload.get('updates', payload)
            result = app.update_config(updates)
            return self._json({'ok': True, **result})

        if route == '/api/config/export' and method == 'GET':
            if not os.path.isfile(app.config_file):
                raise ApiError('配置文件不存在', 404)
            return self._serve_file(app.config_file, download=True, filename='config.ini')

        if route == '/api/config/defaults' and method == 'GET':
            defaults = {}
            for section_name, fields in schema_mod.FIELDS.items():
                defaults[section_name] = {
                    key: (meta.get('default', '') if not isinstance(meta.get('default'), bool)
                          else ('是' if meta['default'] else '否'))
                    for key, meta in fields.items()
                }
            return self._json({'ok': True, 'defaults': defaults})

        # ---------------- 直播间地址
        if route == '/api/urls' and method == 'GET':
            return self._json({'ok': True, **app.get_urls()})

        if route == '/api/urls' and method == 'POST':
            payload = body()
            return self._json(app.add_url(
                payload.get('url', ''), payload.get('quality', ''),
                payload.get('name', ''), payload.get('enabled', True)))

        if route == '/api/urls' and method == 'PUT':
            payload = body()
            if 'index' not in payload:
                raise ApiError('缺少 index 参数')
            return self._json(app.update_url(
                int(payload['index']), payload.get('url'), payload.get('quality'),
                payload.get('name'), payload.get('enabled')))

        if route == '/api/urls/delete' and method == 'POST':
            payload = body()
            return self._json(app.delete_urls(payload.get('indexes', [])))

        if route == '/api/urls/toggle' and method == 'POST':
            payload = body()
            return self._json(app.toggle_urls(payload.get('indexes', []), bool(payload.get('enabled', True))))

        if route == '/api/urls/import' and method == 'POST':
            payload = body()
            return self._json(app.import_urls(payload.get('text', ''), payload.get('mode', 'append')))

        # ---------------- 进程控制
        if route == '/api/control/start' and method == 'POST':
            force = bool(body().get('force', False))
            return self._json(app.control_start(force=force))

        if route == '/api/control/stop' and method == 'POST':
            return self._json(app.control_stop())

        if route == '/api/control/restart' and method == 'POST':
            return self._json(app.control_restart())

        if route == '/api/cookies/sync' and method == 'POST':
            return self._json(app.sync_cookie())

        # ---------------- 日志
        if route == '/api/logs/stream' and method == 'GET':
            return self._stream_logs(arg('since', 0, int))

        if route == '/api/logs/snapshot' and method == 'GET':
            since = arg('since', 0, int)
            limit = arg('limit', 500, int)
            return self._json({
                'ok': True,
                'items': app.recorder.snapshot(since, limit),
                'last_log_id': app.recorder.status()['last_log_id'],
            })

        if route == '/api/logs/clear' and method == 'POST':
            app.recorder.clear_logs()
            return self._json({'ok': True})

        if route == '/api/logs/files' and method == 'GET':
            return self._json({'ok': True, 'items': app.log_files()})

        if route == '/api/logs/tail' and method == 'GET':
            return self._json({'ok': True, **app.tail_log(arg('name', ''), arg('lines', 300, int))})

        # ---------------- 文件
        if route == '/api/files' and method == 'GET':
            target = arg('path') or paths.resolve_save_path(app.project_root)[0]
            roots = app.save_roots()
            try:
                result = files_api.list_dir(
                    target, roots,
                    page=arg('page', 1, int),
                    page_size=max(1, min(arg('page_size', 200, int), 1000)),
                    keyword=arg('keyword', '') or '',
                    recursive=str(arg('recursive', '')).lower() in ('1', 'true', 'yes'),
                )
            except files_api.PathNotAllowed as exc:
                raise ApiError(str(exc), 403) from exc
            except FileNotFoundError as exc:
                raise ApiError(str(exc), 404) from exc
            result['roots'] = roots
            result['root'] = roots[0] if roots else ''
            return self._json({'ok': True, **result})

        if route == '/api/files/delete' and method == 'POST':
            payload = body()
            result = files_api.delete_paths(payload.get('paths', []), app.save_roots())
            return self._json(result)

        if route == '/api/files/download' and method == 'GET':
            target = arg('path', '')
            try:
                full = files_api.resolve_browsable(target)
            except files_api.PathNotAllowed as exc:
                raise ApiError(str(exc), 403) from exc
            if not os.path.isfile(full):
                raise ApiError('文件不存在', 404)
            return self._serve_file(full, download=True, filename=os.path.basename(full))

        if route == '/api/files/stream' and method == 'GET':
            target = arg('path', '')
            try:
                full = files_api.resolve_browsable(target)
            except files_api.PathNotAllowed as exc:
                raise ApiError(str(exc), 403) from exc
            if not os.path.isfile(full):
                raise ApiError('文件不存在', 404)
            return self._serve_file(full, download=False, filename=os.path.basename(full))

        if route == '/api/browse' and method == 'GET':
            return self._json({'ok': True, **files_api.browse_dirs(arg('path', '') or '')})

        if route == '/api/open' and method == 'POST':
            target = body().get('path') or paths.resolve_save_path(app.project_root)[0]
            return self._json(files_api.open_in_file_manager(target))

        # ---------------- 媒体后处理（多段合并 / 裁黑边转 16:9）
        if route == '/api/media/analyze' and method == 'POST':
            payload = body()
            targets = payload.get('paths') or ([payload['path']] if payload.get('path') else [])
            targets = [p for p in targets if p]
            if not targets:
                raise ApiError('请先选择要处理的文件')
            truncated = len(targets) > 24
            targets = targets[:24]
            samples = max(1, min(int(payload.get('samples', 3) or 3), 8))
            try:
                result = media_tools.analyze_selection(
                    targets, samples=samples, project_root=app.project_root)
            except media_tools.MediaError as exc:
                raise ApiError(str(exc)) from exc
            result['truncated'] = truncated
            return self._json({'ok': True, **result})

        if route == '/api/media/merge' and method == 'POST':
            payload = body()
            out_dir = payload.get('out_dir') or None
            if out_dir and not os.path.isdir(out_dir):
                raise ApiError(f'输出目录不存在: {out_dir}')
            try:
                prepared = media_tools.prepare_merge(
                    payload.get('paths') or [], app.project_root,
                    out_dir=out_dir, order=payload.get('order', 'name'))
            except media_tools.MediaError as exc:
                raise ApiError(str(exc)) from exc

            faststart = payload.get('faststart', True) is not False
            drop_source = bool(payload.get('drop_source', False))
            paths_to_merge = prepared['paths']
            output = prepared['output']

            def _run_merge(job, paths_to_merge=paths_to_merge, output=output,
                           faststart=faststart, drop_source=drop_source):
                return media_tools.merge(paths_to_merge, app.project_root, job=job,
                                         faststart=faststart, drop_source=drop_source,
                                         output=output)

            job = app.media_jobs.start(
                'merge', f'合并 {len(paths_to_merge)} 个文件', _run_merge,
                payload={'paths': paths_to_merge, 'output': output})
            return self._json({'ok': True, 'job': job.to_dict(), 'preview': {
                'count': len(paths_to_merge),
                'output': output,
                'total_duration': prepared['total_duration'],
                'warnings': prepared['warnings'],
            }})

        if route == '/api/media/to16x9' and method == 'POST':
            payload = body()
            targets = [p for p in (payload.get('paths') or []) if p]
            if not targets and payload.get('path'):
                targets = [payload['path']]
            if not targets:
                raise ApiError('请先选择要处理的文件')
            out_dir = payload.get('out_dir') or None
            if out_dir and not os.path.isdir(out_dir):
                raise ApiError(f'输出目录不存在: {out_dir}')
            try:
                crf = int(payload.get('crf') or media_tools.DEFAULT_CRF)
            except (TypeError, ValueError):
                raise ApiError('crf 必须是整数') from None
            if not 0 <= crf <= 51:
                raise ApiError('crf 取值范围是 0-51')
            preset = payload.get('preset') or media_tools.DEFAULT_PRESET
            prefer_lossless = payload.get('prefer_lossless', True) is not False
            allow_content_loss = bool(payload.get('allow_content_loss', False))
            drop_source = bool(payload.get('drop_source', False))

            for target in targets:
                if not os.path.isfile(target):
                    raise ApiError(f'文件不存在: {target}')
                try:
                    media_tools.probe(target, app.project_root)
                except media_tools.MediaError as exc:
                    raise ApiError(str(exc)) from exc

            jobs = []
            for target in targets:

                def _run_convert(job, target=target):
                    return media_tools.to_16x9(
                        target, app.project_root, out_dir=out_dir, job=job,
                        prefer_lossless=prefer_lossless, crf=crf, preset=preset,
                        drop_source=drop_source, allow_content_loss=allow_content_loss)

                job = app.media_jobs.start(
                    'to16x9', f'转为 16:9：{os.path.basename(target)}', _run_convert,
                    payload={'path': target})
                jobs.append(job.to_dict())
            return self._json({'ok': True, 'jobs': jobs, 'count': len(jobs)})

        # ---------------- 压缩转码（H.264 / AV1）
        if route == '/api/media/presets' and method == 'GET':
            return self._json({
                'ok': True,
                **media_tools.presets_info(),
                'av1_available': media_tools.is_av1_supported(app.project_root),
            })

        if route == '/api/media/estimate' and method == 'POST':
            payload = body()
            targets = [p for p in (payload.get('paths') or []) if p]
            if not targets:
                raise ApiError('请先选择要压缩的文件')
            level = (payload.get('level') or 'medium').lower()
            if level not in media_tools.COMPRESS_LEVELS:
                raise ApiError(f'不支持的压缩强度: {level}')
            items = []
            for target in targets:
                try:
                    info = media_tools.probe(target, app.project_root)
                    estimate = media_tools.estimate_compress(info, level)
                except media_tools.MediaError as exc:
                    items.append({'path': target, 'name': os.path.basename(target),
                                  'ok': False, 'error': str(exc)})
                    continue
                items.append({
                    'path': target,
                    'name': os.path.basename(target),
                    'ok': estimate.get('ok', False),
                    'error': estimate.get('reason', ''),
                    'source_size': info['size'],
                    'duration': info['duration'],
                    **{k: v for k, v in estimate.items() if k != 'ok'},
                })
            total_source = sum(i.get('source_size') or 0 for i in items)
            total_estimated = sum(i.get('estimated_size') or 0 for i in items)
            return self._json({
                'ok': True, 'items': items, 'level': level,
                'total_source': total_source, 'total_estimated': total_estimated,
                'total_ratio': round(total_estimated / total_source, 4) if total_source else None,
            })

        if route == '/api/media/compress' and method == 'POST':
            payload = body()
            targets = [p for p in (payload.get('paths') or []) if p]
            if not targets:
                raise ApiError('请先选择要压缩的文件')
            codec = (payload.get('codec') or 'h264').lower()
            level = (payload.get('level') or 'medium').lower()
            if codec not in media_tools.CODEC_SETTINGS:
                raise ApiError(f'不支持的编码器: {codec}')
            if level not in media_tools.COMPRESS_LEVELS:
                raise ApiError(f'不支持的压缩强度: {level}')
            if codec == 'av1' and not media_tools.is_av1_supported(app.project_root):
                raise ApiError('当前 ffmpeg 不包含 AV1 编码器（libsvtav1），请升级 ffmpeg')
            crop_to_16x9 = payload.get('crop_to_16x9', True) is not False
            allow_content_loss = bool(payload.get('allow_content_loss', False))
            out_dir = payload.get('out_dir') or None
            if out_dir and not os.path.isdir(out_dir):
                raise ApiError(f'输出目录不存在: {out_dir}')

            for target in targets:
                if not os.path.isfile(target):
                    raise ApiError(f'文件不存在: {target}')
                try:
                    media_tools.probe(target, app.project_root)
                except media_tools.MediaError as exc:
                    raise ApiError(str(exc)) from exc

            jobs = []
            for target in targets:

                def _run_compress(job, target=target, codec=codec, level=level,
                                  crop_to_16x9=crop_to_16x9, allow=allow_content_loss):
                    return media_tools.compress(
                        target, app.project_root, out_dir=out_dir, job=job,
                        codec=codec, level=level, crop_to_16x9=crop_to_16x9,
                        allow_content_loss=allow)

                job = app.media_jobs.start(
                    'compress', f'压缩（{codec.upper()}）：{os.path.basename(target)}',
                    _run_compress, payload={'path': target})
                jobs.append(job.to_dict())
            return self._json({'ok': True, 'jobs': jobs, 'count': len(jobs)})

        if route == '/api/media/jobs' and method == 'GET':
            return self._json({
                'ok': True,
                'items': app.media_jobs.list(limit=max(1, min(arg('limit', 40, int), 200))),
                'active': app.media_jobs.active_count(),
            })

        if route == '/api/media/jobs/cancel' and method == 'POST':
            job_id = body().get('id') or ''
            if not job_id:
                raise ApiError('缺少任务 id')
            cancelled = app.media_jobs.cancel(job_id)
            return self._json({'ok': cancelled, 'id': job_id,
                               'error': '' if cancelled else '任务不存在或已结束'})

        raise ApiError(f'接口不存在: {method} {route}', 404)

    # ------------------------------------------------------------ SSE
    def _stream_logs(self, since: int):
        recorder = self.app.recorder
        subscriber = recorder.subscribe()
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('Connection', 'close')
            self.send_header('X-Accel-Buffering', 'no')
            self.end_headers()
            self.close_connection = True

            self._sse({'type': 'hello', 'server_time': time.time(), 'version': self.app.version})
            for entry in recorder.snapshot(since, limit=800):
                self._sse({'type': 'log', 'entry': entry})
            self._sse({'type': 'status', 'status': recorder.status()})

            last_ping = time.time()
            last_status = time.time()
            while not self.app._stop_event.is_set():
                try:
                    entry = subscriber.get(timeout=10)
                except queue.Empty:
                    entry = None
                if entry is not None:
                    self._sse({'type': 'log', 'entry': entry})
                    continue
                now = time.time()
                if now - last_ping > 15:
                    self.wfile.write(b': ping\n\n')
                    self.wfile.flush()
                    last_ping = now
                if now - last_status > 5:
                    self._sse({'type': 'status', 'status': recorder.status()})
                    last_status = now
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            pass
        finally:
            recorder.unsubscribe(subscriber)

    def _sse(self, payload: dict):
        data = json.dumps(payload, ensure_ascii=False, default=json_default)
        self.wfile.write(f'data: {data}\n\n'.encode('utf-8'))
        self.wfile.flush()

    # ------------------------------------------------------------ 静态文件
    def _serve_static(self, route: str):
        if route in ('/', '/index.html'):
            target = os.path.join(STATIC_DIR, 'index.html')
        else:
            rel = route.lstrip('/')
            if rel.startswith('static/'):
                rel = rel[len('static/'):]
            target = os.path.normpath(os.path.join(STATIC_DIR, rel))
            if not os.path.normcase(target).startswith(os.path.normcase(STATIC_DIR)):
                raise ApiError('非法的静态资源路径', 403)
        if not os.path.isfile(target):
            raise ApiError(f'资源不存在: {route}', 404)
        # 每次回源校验，避免更新前端后刷新页面仍加载旧的 app.js / style.css
        return self._serve_file(target, download=False, cache_control='no-cache')

    # ------------------------------------------------------------ 文件下发
    def _serve_file(self, full_path: str, download: bool = False, filename: str = '',
                    cache_control: str = ''):
        try:
            stat = os.stat(full_path)
        except OSError as exc:
            raise ApiError(f'无法读取文件: {exc}', 404) from exc

        size = stat.st_size
        name = filename or os.path.basename(full_path)
        ext = os.path.splitext(name)[1].lower()
        ctype = MIME_OVERRIDES.get(ext) or mimetypes.guess_type(name)[0] or 'application/octet-stream'
        if ext in files_api.VIDEO_EXT and ext != '.ts':
            ctype = mimetypes.guess_type(name)[0] or 'video/mp4'
        if ext == '.ts':
            ctype = 'video/mp2t'

        start, end = 0, max(size - 1, 0)
        status = 200
        range_header = self.headers.get('Range')
        if range_header:
            match = re.match(r'bytes=(\d*)-(\d*)\s*$', range_header.strip())
            if match:
                first, last = match.group(1), match.group(2)
                if first:
                    start = int(first)
                if last:
                    end = int(last)
                elif not first and last:
                    start = max(0, size - int(last))
                    end = size - 1
                if not first and not last:
                    start, end = 0, size - 1
                if start >= size or start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                status = 206

        length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(length))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Last-Modified', self.date_time_string(stat.st_mtime))
        if cache_control:
            self.send_header('Cache-Control', cache_control)
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if download:
            ascii_name = re.sub(r'[^\x20-\x7e]', '_', name).replace('"', '')
            self.send_header(
                'Content-Disposition',
                f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(name)}'
            )
        self.end_headers()

        if self.command == 'HEAD':
            return
        remaining = length
        with open(full_path, 'rb') as fp:
            fp.seek(start)
            while remaining > 0:
                chunk = fp.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_HEAD(self):
        self._dispatch('GET')


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, app: WebConsole, token: str = ''):
        super().__init__(address, handler)
        ConsoleHandler.app = app
        ConsoleHandler.token = token


def find_free_port(host: str, preferred: int) -> int:
    for port in [preferred] + [preferred + offset for offset in range(1, 25)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f'端口 {preferred} 及相邻端口都被占用，请用 --port 指定其它端口')


# ---------------------------------------------------------------- 后台运行支持

PID_FILE_REL = os.path.join('logs', 'console.pid')


def ensure_std_streams(project_root: str) -> None:
    """用 pythonw.exe 启动时没有控制台，sys.stdout/stderr 会是 None。

    此时任何 print() 都会抛 AttributeError 把进程打死，所以把它们重定向到
    logs/console.log —— 后台模式既不丢日志，也不会因为一句 print 崩掉。
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        stream = open(os.path.join(log_dir, 'console.log'), 'a',
                      encoding='utf-8', buffering=1)
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def write_pid_file(project_root: str, port: int) -> str:
    """记录 pid 和实际端口，供后台停止脚本使用（端口可能因占用而顺延）。"""
    path = os.path.join(project_root, PID_FILE_REL)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(f'{os.getpid()}\n{port}\n')
        return path
    except OSError:
        return ''


def remove_pid_file(path: str) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description='DouyinLiveRecorder 可视化控制台')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址，默认 127.0.0.1（仅本机可访问）')
    parser.add_argument('--port', type=int, default=8765, help='监听端口，默认 8765')
    parser.add_argument('--python', default='', help='用于运行 main.py 的 Python 解释器，默认自动选择 .venv 或当前解释器')
    parser.add_argument('--token', default='', help='可选的访问令牌，设置后访问需要 ?token=xxx')
    parser.add_argument('--open', action='store_true', help='启动后自动打开浏览器')
    parser.add_argument('--project-root', default=paths.PROJECT_ROOT, help='项目根目录')
    args = parser.parse_args()

    project_root = os.path.abspath(args.project_root)
    ensure_std_streams(project_root)      # pythonw 后台模式没有控制台，先把输出接住
    python_exe = args.python or paths.pick_python(project_root)
    port = find_free_port(args.host, args.port)

    app = WebConsole(project_root, python_exe, host=args.host, port=port)
    app.ensure_config()
    app.ensure_url_file()
    app.ensure_schema_keys()
    app.ensure_dirs()

    server = ConsoleServer((args.host, port), ConsoleHandler, app, token=args.token)
    url = f'http://{"127.0.0.1" if args.host in ("0.0.0.0", "") else args.host}:{port}/'
    if args.token:
        url += f'?token={args.token}'

    print('=' * 62)
    print('  DouyinLiveRecorder 可视化控制台已启动')
    print(f'  访问地址: {url}')
    print(f'  项目目录: {project_root}')
    print(f'  录制解释器: {python_exe}')
    print('  按 Ctrl+C 退出（不会停止正在进行的录制，请在网页上停止）')
    print('=' * 62)

    if args.host not in ('127.0.0.1', 'localhost'):
        print('  [!] 当前监听非本机地址，请确认网络环境可信，必要时配合 --token 使用')

    if args.open and os.environ.get('DLR_NO_BROWSER') != '1':
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    pid_file = write_pid_file(project_root, port)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print('\n正在关闭可视化控制台 ...')
    finally:
        remove_pid_file(pid_file)
        app._stop_event.set()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
