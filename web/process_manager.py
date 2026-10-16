# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 录制进程管理

* 以子进程方式启动 main.py（不修改其运行逻辑），实时捕获 stdout/stderr；
* 环形缓冲保存最近日志，支持多客户端订阅（SSE 推送）；
* 从日志里解析运行状态（监测数 / 录制数 / 错误数 / 磁盘剩余），供仪表盘展示；
* 停止时结束整棵进程树，避免 ffmpeg 变成孤儿进程继续写文件。
"""

import collections
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
LEVEL_RE = re.compile(r'\|\s*(TRACE|DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*[|\-]', re.IGNORECASE)

STAT_PATTERNS = {
    'monitoring': re.compile(r'共监测\s*(\d+)\s*个直播'),
    'recording_count': re.compile(r'正在录制\s*(\d+)\s*个直播'),
    'error_count': re.compile(r'目前瞬时错误数为[:：]\s*(\d+)'),
    'quality': re.compile(r'录制视频质量为[:：]\s*(\S+)'),
    'video_format': re.compile(r'录制视频格式为[:：]\s*(\S+)'),
    'free_space': re.compile(r'Free:\s*([\d.]+)\s*GB'),
}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)


def detect_level(text: str) -> str:
    match = LEVEL_RE.search(text)
    if match:
        return match.group(1).upper()
    lowered = text.lower()
    if 'traceback (most recent call last)' in lowered:
        return 'ERROR'
    if '错误' in text and ('失败' in text or 'error' in lowered):
        return 'ERROR'
    if '警告' in text or '失败' in text:
        return 'WARNING'
    return 'OUT'


class RecorderProcess:
    """包装 main.py 子进程。"""

    def __init__(self, project_root: str, python_exe: str = None, buffer_size: int = 4000):
        self.project_root = os.path.abspath(project_root)
        self.python_exe = python_exe or sys.executable
        self.buffer_size = buffer_size

        self._lock = threading.RLock()
        self._proc = None
        self._reader = None
        self._log_id = 0
        self._logs = collections.deque(maxlen=buffer_size)
        self._subscribers = set()

        self.started_at = None
        self.stopped_at = None
        self.exit_code = None
        self.last_start_error = ''
        self.user_stopped = False
        self.stats = {
            'monitoring': 0,
            'recording_count': 0,
            'error_count': 0,
            'quality': '',
            'video_format': '',
            'free_space': None,
        }

    # ------------------------------------------------------------ 属性
    @property
    def running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def is_running(self) -> bool:
        return self.running

    # ------------------------------------------------------------ 启动
    def start(self) -> dict:
        with self._lock:
            if self.running:
                return {'ok': False, 'error': '录制进程已在运行中'}
            if not os.path.isfile(os.path.join(self.project_root, 'main.py')):
                return {'ok': False, 'error': f'未找到 main.py：{self.project_root}'}

            env = os.environ.copy()
            env['DLR_HEADLESS'] = '1'          # 关闭清屏与交互式 input
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'

            popen_kwargs = {}
            if os.name == 'nt':
                popen_kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | \
                    getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            else:
                popen_kwargs['start_new_session'] = True

            cmd = [self.python_exe, '-u', 'main.py']
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=self.project_root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    **popen_kwargs,
                )
            except OSError as exc:
                self.last_start_error = str(exc)
                self._proc = None
                return {'ok': False, 'error': f'启动失败: {exc}'}

            self.started_at = time.time()
            self.stopped_at = None
            self.exit_code = None
            self.last_start_error = ''
            self.user_stopped = False
            for key in self.stats:
                self.stats[key] = 0 if isinstance(self.stats[key], int) else \
                    (None if key == 'free_space' else '')

            self._emit('SYS', f'已启动录制进程 (PID {self._proc.pid})：{" ".join(cmd)}', level='INFO')
            self._reader = threading.Thread(target=self._read_loop, args=(self._proc,), daemon=True)
            self._reader.start()
            return {'ok': True, 'pid': self._proc.pid}

    # ------------------------------------------------------------ 停止
    def stop(self, timeout: float = 2.5) -> dict:
        """停止录制进程。

        Windows 下控制台子进程不会响应 taskkill 的软关闭，因此这里只做很短的
        等待就强制结束整棵进程树——否则 ffmpeg 会变成孤儿进程继续写文件。
        """
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                return {'ok': True, 'already_stopped': True}
            pid = proc.pid
            self.user_stopped = True
            self._emit('SYS', f'正在停止录制进程 (PID {pid}) ...', level='WARNING')

        self._terminate_tree(pid, force=False)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.2)
        if proc.poll() is None:
            with self._lock:
                self._emit('SYS', '正在结束进程树（含 ffmpeg 子进程）', level='WARNING')
            self._terminate_tree(pid, force=True)
            try:
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                pass
        with self._lock:
            self.stopped_at = time.time()
            self._emit('SYS', f'录制进程已停止，退出码 {proc.poll()}', level='INFO')
        return {'ok': True, 'exit_code': proc.poll()}

    @staticmethod
    def _terminate_tree(pid: int, force: bool = False) -> None:
        if os.name == 'nt':
            taskkill = shutil.which('taskkill') or 'taskkill'
            cmd = [taskkill, '/PID', str(pid), '/T']
            if force:
                cmd.append('/F')
            try:
                subprocess.run(cmd, capture_output=True, timeout=20)
            except Exception:
                try:
                    if force:
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
                except Exception:
                    pass
        else:
            try:
                pgid = os.getpgid(pid)
            except OSError:
                pgid = None
            sig = signal.SIGKILL if force else signal.SIGTERM
            try:
                if pgid is not None:
                    os.killpg(pgid, sig)
                else:
                    os.kill(pid, sig)
            except OSError:
                pass

    def restart(self) -> dict:
        if self.running:
            self.stop()
        time.sleep(0.6)
        return self.start()

    # ------------------------------------------------------------ 日志
    def _read_loop(self, proc: subprocess.Popen) -> None:
        stream = proc.stdout
        try:
            while True:
                chunk = stream.readline()
                if not chunk:
                    break
                for text in self._split_chunk(chunk):
                    self._handle_line(text)
        except (ValueError, OSError):
            pass
        finally:
            code = proc.wait()
            with self._lock:
                self.exit_code = code
                self.stopped_at = time.time()
                if self.user_stopped:
                    level = 'INFO'
                else:
                    level = 'INFO' if code == 0 else 'ERROR'
                self._emit('SYS', f'录制进程已退出，退出码 {code}', level=level)

    @staticmethod
    def _split_chunk(chunk: str):
        """readline 以 \\n 结尾（最后一行除外），据此切分并去掉尾部空串。"""
        chunk = chunk.replace('\r\n', '\n')
        parts = chunk.split('\n')
        for part in parts[:-1]:
            yield part
        if parts[-1]:
            yield parts[-1]

    def _handle_line(self, raw: str) -> None:
        text = strip_ansi(raw).rstrip()
        if not text:
            return
        # 进度类输出用 \r 刷新，只保留最后一段
        if '\r' in text:
            text = text.split('\r')[-1].strip()
        if not text:
            return
        level = detect_level(text)
        with self._lock:
            for name, pattern in STAT_PATTERNS.items():
                match = pattern.search(text)
                if not match:
                    continue
                value = match.group(1)
                if name == 'free_space':
                    try:
                        self.stats[name] = float(value)
                    except ValueError:
                        pass
                elif name in ('quality', 'video_format'):
                    self.stats[name] = value
                else:
                    try:
                        self.stats[name] = int(value)
                    except ValueError:
                        pass
        self._emit('OUT', text, level=level)

    def _emit(self, source: str, text: str, level: str = 'OUT') -> None:
        self._log_id += 1
        entry = {
            'id': self._log_id,
            'ts': time.time(),
            'source': source,
            'level': level,
            'text': text,
        }
        self._logs.append(entry)
        dead = []
        for sub in list(self._subscribers):
            try:
                sub.put_nowait(entry)
            except queue.Full:
                dead.append(sub)
            except Exception:
                dead.append(sub)
        for sub in dead:
            self._subscribers.discard(sub)

    def snapshot(self, since_id: int = 0, limit: int = 600) -> list:
        with self._lock:
            items = [e for e in self._logs if e['id'] > since_id]
        return items[-limit:]

    # ------------------------------------------------------------ 订阅
    def subscribe(self) -> queue.Queue:
        sub = queue.Queue(maxsize=2000)
        with self._lock:
            self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()

    # ------------------------------------------------------------ 状态
    def status(self) -> dict:
        running = self.running
        with self._lock:
            proc = self._proc
            pid = proc.pid if proc is not None else None
            if not running and proc is not None and self.exit_code is None:
                self.exit_code = proc.poll()
            uptime = (time.time() - self.started_at) if (running and self.started_at) else 0
            return {
                'running': running,
                'pid': pid,
                'started_at': self.started_at,
                'stopped_at': self.stopped_at,
                'uptime': round(uptime, 1),
                'exit_code': self.exit_code,
                'user_stopped': self.user_stopped,
                'python': self.python_exe,
                'project_root': self.project_root,
                'stats': dict(self.stats),
                'last_log_id': self._log_id,
                'start_error': self.last_start_error,
            }


# ---------------------------------------------------------------- 环境探测
class EnvironmentProbe:
    """检测运行环境：依赖包、ffmpeg、磁盘空间（带缓存）。"""

    REQUIRED_MODULES = ['requests', 'loguru', 'httpx', 'execjs', 'Crypto']

    def __init__(self, project_root: str, python_exe: str, ttl: float = 30.0):
        self.project_root = project_root
        self.python_exe = python_exe
        self.ttl = ttl
        self._cache = {}
        self._cache_at = 0.0
        self._lock = threading.Lock()

    def _probe_python(self) -> dict:
        import json
        code = (
            'import importlib.util as u, json, sys\n'
            f'mods = {self.REQUIRED_MODULES!r}\n'
            'missing = [m for m in mods if u.find_spec(m) is None]\n'
            "print(json.dumps({'missing': missing, 'executable': sys.executable}))\n"
        )
        try:
            result = subprocess.run(
                [self.python_exe, '-c', code],
                capture_output=True, text=True, timeout=25,
                cwd=self.project_root, encoding='utf-8', errors='replace',
            )
            if result.returncode != 0:
                return {'ok': False, 'missing': list(self.REQUIRED_MODULES),
                        'executable': self.python_exe,
                        'error': (result.stderr or '').strip()[-500:]}
            payload = json.loads((result.stdout or '{}').strip().splitlines()[-1])
            return {'ok': not payload.get('missing'), 'missing': payload.get('missing', []),
                    'executable': payload.get('executable', self.python_exe)}
        except Exception as exc:
            return {'ok': False, 'missing': list(self.REQUIRED_MODULES),
                    'executable': self.python_exe, 'error': str(exc)}

    def _probe_ffmpeg(self) -> dict:
        local = os.path.join(self.project_root, 'ffmpeg')
        candidates = []
        if os.path.isdir(local):
            for root, _dirs, files in os.walk(local):
                for name in files:
                    if name.lower().startswith('ffmpeg'):
                        candidates.append(os.path.join(root, name))
        which = shutil.which('ffmpeg')
        if which:
            candidates.append(which)
        for path in candidates:
            try:
                result = subprocess.run([path, '-version'], capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    first = (result.stdout or '').splitlines()[0] if result.stdout else 'ffmpeg'
                    return {'ok': True, 'path': path, 'version': first.strip()}
            except Exception:
                continue
        return {'ok': False, 'path': '', 'version': '', 'error': '未找到 ffmpeg'}

    def _probe_disk(self) -> dict:
        import paths
        path, source = paths.resolve_save_path(self.project_root)
        try:
            usage = shutil.disk_usage(path)
            return {
                'ok': True,
                'path': path,
                'source': source,
                'total_gb': round(usage.total / 1024 ** 3, 2),
                'used_gb': round(usage.used / 1024 ** 3, 2),
                'free_gb': round(usage.free / 1024 ** 3, 2),
            }
        except OSError as exc:
            return {'ok': False, 'path': path, 'error': str(exc)}

    def get(self, force: bool = False) -> dict:
        with self._lock:
            now = time.time()
            if not force and self._cache and (now - self._cache_at) < self.ttl:
                return self._cache
            self._cache = {
                'dependencies': self._probe_python(),
                'ffmpeg': self._probe_ffmpeg(),
                'disk': self._probe_disk(),
                'checked_at': now,
            }
            self._cache_at = now
            return self._cache
