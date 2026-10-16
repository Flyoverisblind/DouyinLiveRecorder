# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 配置文件读写

设计目标：
1. 只依赖 Python 标准库；
2. 修改配置时 **不破坏** config.ini 原有的注释、空行、键顺序、BOM 与换行符，
   因为使用者经常手工维护这个文件（configparser 回写会丢掉全部注释）；
3. 写入使用「临时文件 + 原子替换」，避免与 main.py 同时写导致文件损坏。
"""

import os
import re
import threading
import time

ENCODING = 'utf-8-sig'

# config.ini 中所有出现的段（与 main.py 中的定义保持一致）
KNOWN_SECTIONS = ['录制设置', '推送配置', 'Cookie', 'Authorization', '账号密码']

_SECTION_RE = re.compile(r'^\[(.+?)\]\s*$')
_ILLEGAL_VALUE_CHARS = re.compile(r'[\r\n]+')

# 进程内写锁：同一个控制台进程内的并发请求串行化
_write_lock = threading.RLock()


def sanitize_value(value) -> str:
    """把任意输入转换成可以安全写入 ini 单行的字符串。"""
    if value is None:
        return ''
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, (list, tuple, set)):
        value = ', '.join(str(v) for v in value)
    text = _ILLEGAL_VALUE_CHARS.sub(' ', str(value))
    return text.strip()


def split_line_ending(line: str) -> tuple:
    if line.endswith('\r\n'):
        return line[:-2], '\r\n'
    if line.endswith('\n'):
        return line[:-1], '\n'
    if line.endswith('\r'):
        return line[:-1], '\r'
    return line, ''


class IniDocument:
    """以「行」为单位保存 ini 文件，尽量做到无损修改。"""

    def __init__(self, path: str, encoding: str = ENCODING):
        self.path = path
        self.encoding = encoding
        self.lines = []                # 原始行（含换行符）
        self.order = []                # 段落出现顺序
        self.header_index = {}         # 段落名 -> 段头所在行号
        self.key_index = {}            # 段落名 -> {键: 行号}
        self.values = {}               # 段落名 -> {键: 值}（有序）
        self.extra_keys = {}           # 段落名 -> [未识别的键...]（保序）
        self.exists = False

    # ---------------------------------------------------------------- 读取
    def load(self) -> 'IniDocument':
        self.lines, self.order, self.header_index = [], [], {}
        self.key_index, self.values, self.extra_keys = {}, {}, {}
        self.exists = os.path.isfile(self.path)
        if not self.exists:
            return self

        with open(self.path, 'r', encoding=self.encoding, newline='') as fp:
            text = fp.read()
        if not text:
            return self

        self.lines = text.splitlines(keepends=True)
        current = None
        for idx, raw in enumerate(self.lines):
            body, _eol = split_line_ending(raw)
            stripped = body.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith(';'):
                continue
            match = _SECTION_RE.match(stripped)
            if match:
                current = match.group(1).strip()
                if current not in self.header_index:
                    self.order.append(current)
                    self.header_index[current] = idx
                    self.key_index[current] = {}
                    self.values[current] = {}
                    self.extra_keys[current] = []
                continue
            if current is None or '=' not in body:
                continue
            key = body.split('=', 1)[0].strip()
            if not key:
                continue
            # 重复键：以最后一次出现的为准（与 configparser 行为一致）
            self.key_index[current][key] = idx
            self.values[current][key] = body.split('=', 1)[1].strip()
            if key not in self.extra_keys[current]:
                self.extra_keys[current].append(key)
        return self

    # ---------------------------------------------------------------- 查询
    def get(self, section: str, key: str, default: str = '') -> str:
        return self.values.get(section, {}).get(key, default)

    def section_items(self, section: str) -> dict:
        return dict(self.values.get(section, {}))

    def default_line_ending(self) -> str:
        for raw in self.lines:
            _body, eol = split_line_ending(raw)
            if eol:
                return eol
        return '\n'

    # ---------------------------------------------------------------- 修改
    def _section_bounds(self, section: str) -> tuple:
        """返回 (段头行号, 段内容结束行号)。段不存在时返回 (-1, len(lines)-1)。"""
        if section not in self.header_index:
            return -1, len(self.lines) - 1
        start = self.header_index[section]
        end = len(self.lines)
        for other in self.order:
            idx = self.header_index[other]
            if idx > start and idx < end:
                end = idx
        return start, end

    def set_value(self, section: str, key: str, value) -> bool:
        """写入单个配置项，返回是否发生了实际改动。"""
        value = sanitize_value(value)
        if section in self.key_index and key in self.key_index[section]:
            idx = self.key_index[section][key]
            raw = self.lines[idx]
            body, eol = split_line_ending(raw)
            eq = body.find('=')
            head = body[:eq + 1]
            rest = body[eq + 1:]
            sep = re.match(r'[ \t]*', rest).group(0) or ' '
            if self.values[section].get(key) == value:
                return False
            self.lines[idx] = f'{head}{sep}{value}{eol}'
            self.values[section][key] = value
            return True

        # 新增键：追加到该段末尾（跳过段尾的空行，保持在段内）
        eol = self.default_line_ending()
        new_line = f'{key} = {value}{eol}'
        if section not in self.header_index:
            prefix = [] if (not self.lines or self.lines[-1].endswith(('\n', '\r'))) else [eol]
            block = prefix + [f'[{section}]{eol}', new_line]
            self.lines.extend(block)
            base = len(self.lines) - len(block)
            self.order.append(section)
            self.header_index[section] = base
            self.key_index[section] = {key: base + len(prefix) + 1}
            self.values[section] = {key: value}
            self.extra_keys[section] = [key]
            return True

        _start, end = self._section_bounds(section)
        insert_at = end
        while insert_at - 1 > self.header_index[section]:
            body, _eol = split_line_ending(self.lines[insert_at - 1])
            if body.strip():
                break
            insert_at -= 1
        eol = self.default_line_ending()
        self.lines.insert(insert_at, f'{key} = {value}{eol}')
        # 后续行号整体后移
        for name in self.order:
            if self.header_index[name] >= insert_at:
                self.header_index[name] += 1
            for k, v in self.key_index.get(name, {}).items():
                if v >= insert_at:
                    self.key_index[name][k] = v + 1
        self.key_index[section][key] = insert_at
        self.values[section][key] = value
        self.extra_keys.setdefault(section, []).append(key)
        return True

    def to_text(self) -> str:
        return ''.join(self.lines)

    # ---------------------------------------------------------------- 保存
    def save(self) -> None:
        directory = os.path.dirname(os.path.abspath(self.path)) or '.'
        os.makedirs(directory, exist_ok=True)
        tmp_path = f'{self.path}.{os.getpid()}.tmp'
        with open(tmp_path, 'w', encoding=self.encoding, newline='') as fp:
            fp.write(self.to_text())
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, self.path)
        self.exists = True


def update_config_file(path: str, updates: dict, encoding: str = ENCODING) -> dict:
    """把 {段: {键: 值}} 写入配置文件。

    返回 {'ok': bool, 'changed': [ '段.键', ... ], 'backup': 备份文件路径}
    """
    with _write_lock:
        doc = IniDocument(path, encoding).load()
        changed = []
        for section, items in (updates or {}).items():
            if not isinstance(items, dict):
                continue
            for key, value in items.items():
                try:
                    if doc.set_value(section, key, value):
                        changed.append(f'{section}.{key}')
                except Exception as exc:  # 单个键失败不影响其它键
                    raise RuntimeError(f'写入 {section}.{key} 失败: {exc}') from exc
        backup = None
        if changed:
            backup = backup_file(path)
            doc.save()
        return {'ok': True, 'changed': changed, 'backup': backup}


def backup_file(path: str, keep: int = 20) -> str:
    """写入前备份，最多保留 keep 份。"""
    if not os.path.isfile(path):
        return ''
    directory = os.path.dirname(os.path.abspath(path))
    backup_dir = os.path.join(directory, 'backup')
    try:
        os.makedirs(backup_dir, exist_ok=True)
        name = os.path.basename(path)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        target = os.path.join(backup_dir, f'{name}.{stamp}.bak')
        if not os.path.exists(target):
            with open(path, 'rb') as src, open(target, 'wb') as dst:
                dst.write(src.read())
        olds = sorted(
            (os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
             if f.startswith(name) and f.endswith('.bak')),
            key=os.path.getmtime,
        )
        for old in olds[:-keep]:
            try:
                os.remove(old)
            except OSError:
                pass
        return target
    except OSError:
        return ''


def read_config_values(path: str, encoding: str = ENCODING) -> dict:
    doc = IniDocument(path, encoding).load()
    return {section: dict(items) for section, items in doc.values.items()}


# ------------------------------------------------------------------ URL 列表
class UrlEntry:
    """URL_config.ini 中的一行。

    行格式（与 main.py 的解析逻辑一致）::

        [画质,] 直播间地址 [,主播名]
        #画质, 直播间地址, 主播名      -> 以 # 开头表示停用（main.py 称之为「注释」）
    """

    def __init__(self, index: int, raw: str):
        self.index = index
        self.raw = raw
        self.enabled = True
        self.quality = ''
        self.url = ''
        self.name = ''
        self.valid = False
        self.parse(raw)

    def parse(self, raw: str) -> None:
        line = raw.strip()
        self.enabled = not line.startswith('#')
        if not self.enabled:
            line = line.lstrip('#').strip()
        parts = [p.strip() for p in re.split(r'[,，]', line)] if line else ['']
        if len(parts) >= 3:
            self.quality, self.url, self.name = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            if self._looks_like_url(parts[0]) or not parts[0]:
                self.url, self.name = parts[0], parts[1]
            else:
                self.quality, self.url = parts[0], parts[1]
        else:
            self.url = parts[0]
        self.valid = bool(self._looks_like_url(self.url))

    @staticmethod
    def _looks_like_url(text: str) -> bool:
        if not text:
            return False
        return bool(re.search(r'^(https?://)?[\w.-]+\.[a-zA-Z]{2,}', text)) or \
            any(ext in text for ext in ('.flv', '.m3u8'))

    def to_line(self) -> str:
        chunks = []
        if self.quality:
            chunks.append(self.quality)
        chunks.append(self.url)
        if self.name:
            chunks.append(self.name)
        line = ', '.join(chunks)
        return f'#{line}' if not self.enabled else line

    def to_dict(self) -> dict:
        return {
            'index': self.index,
            'raw': self.raw,
            'enabled': self.enabled,
            'quality': self.quality,
            'url': self.url,
            'name': self.name,
            'valid': self.valid,
            'line': self.to_line(),
        }


def read_url_file(path: str, encoding: str = ENCODING) -> list:
    """读取 URL_config.ini，返回全部非空行的 UrlEntry 列表。"""
    entries = []
    if not os.path.isfile(path):
        return entries
    with _write_lock:
        with open(path, 'r', encoding=encoding, newline='') as fp:
            lines = fp.read().splitlines()
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        entries.append(UrlEntry(idx, line))
    return entries


def read_url_lines(path: str, encoding: str = ENCODING) -> list:
    """读取 URL_config.ini 的全部原始行（含空行，保留行号对应关系）。"""
    if not os.path.isfile(path):
        return []
    with _write_lock:
        with open(path, 'r', encoding=encoding, newline='') as fp:
            return fp.read().splitlines()


def write_url_lines(path: str, lines: list, encoding: str = ENCODING) -> None:
    """整体写回 URL_config.ini。

    换行符沿用文件原有的风格：main.py 在 Windows 上会把它规范成 CRLF，
    这里跟着走，避免两边来回改写时文件反复变动。
    """
    with _write_lock:
        eol = '\n'
        if os.path.isfile(path):
            with open(path, 'rb') as probe:
                head = probe.read()
            if b'\r\n' in head:
                eol = '\r\n'
            elif b'\n' in head:
                eol = '\n'
        backup_file(path)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp_path = f'{path}.{os.getpid()}.tmp'
        body = eol.join(line.rstrip() for line in lines)
        if body:
            body += eol
        with open(tmp_path, 'w', encoding=encoding, newline='') as fp:
            fp.write(body)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, path)
