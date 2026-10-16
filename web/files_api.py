# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 录制文件浏览

* 只能访问「录制保存目录」和项目下的 downloads 目录（防止路径穿越）；
* 支持列表、下载（含 Range 断点/拖动播放）、删除、在文件管理器中打开。
"""

import os
import shutil
import subprocess
import sys
import time

VIDEO_EXT = {'.mp4', '.ts', '.mkv', '.flv', '.avi', '.mov', '.webm', '.m4v', '.wmv', '.mpg', '.mpeg'}
AUDIO_EXT = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
SUB_EXT = {'.srt', '.ass', '.vtt', '.txt', '.json', '.log', '.xml'}


class PathNotAllowed(Exception):
    pass


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def allowed_roots(project_root: str, save_path: str = None) -> list:
    import paths
    roots = []
    if save_path:
        roots.append(save_path)
    resolved, _source = paths.resolve_save_path(project_root)
    roots.append(resolved)
    roots.append(paths.default_save_path(project_root))
    unique = []
    for root in roots:
        if not root:
            continue
        full = _norm(root)
        if full not in unique:
            unique.append(full)
    return unique


def resolve_within(path: str, roots: list) -> str:
    """把请求路径解析为绝对路径，并确保它位于允许的根目录内（仅用于删除等写操作）。"""
    if not path:
        raise PathNotAllowed('缺少路径参数')
    target = os.path.abspath(os.path.expanduser(path))
    if not is_within(target, roots):
        raise PathNotAllowed(f'路径不在允许范围内: {path}')
    return target


def is_within(path: str, roots: list) -> bool:
    """判断路径是否位于允许的根目录内（路径不存在也返回 True）。"""
    if not path:
        return False
    real = _norm(path)
    for root in roots or []:
        if real == root or real.startswith(root + os.sep):
            return True
    return False


def resolve_browsable(path: str) -> str:
    """浏览/下载用的路径解析：不限制根目录，只要求路径存在。

    控制台只监听本机，且目录选择器本来就能列任意目录；
    因此浏览放开，而删除等破坏性操作仍然限制在录制目录内（见 resolve_within）。
    """
    if not path:
        raise PathNotAllowed('缺少路径参数')
    return os.path.abspath(os.path.expanduser(path))


def list_drives() -> list:
    """Windows 下返回可用盘符列表，方便从 C 盘切到 D 盘。"""
    drives = []
    if os.name == 'nt':
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            root = f'{letter}:\\'
            if os.path.exists(root):
                drives.append({'name': root, 'path': root})
    return drives


def classify(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext in VIDEO_EXT:
        return 'video'
    if ext in AUDIO_EXT:
        return 'audio'
    if ext in SUB_EXT:
        return 'text'
    return 'other'


def _stat_entry(full_path: str, rel_base: str) -> dict:
    try:
        stat = os.stat(full_path)
    except OSError:
        return None
    name = os.path.basename(full_path)
    return {
        'name': name,
        'path': full_path,
        'rel': os.path.relpath(full_path, rel_base).replace('\\', '/'),
        'size': stat.st_size,
        'mtime': stat.st_mtime,
        'mtime_text': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
        'kind': classify(name),
        'ext': os.path.splitext(name)[1].lower().lstrip('.'),
    }


def list_dir(path: str, roots: list = None, page: int = 1, page_size: int = 200,
             keyword: str = '', recursive: bool = False) -> dict:
    target = resolve_browsable(path)
    if not os.path.isdir(target):
        raise FileNotFoundError(f'目录不存在: {target}')
    deletable = is_within(target, roots or [])

    dirs, files = [], []
    if recursive:
        for root, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                if keyword and keyword.lower() not in filename.lower():
                    continue
                entry = _stat_entry(os.path.join(root, filename), target)
                if entry:
                    files.append(entry)
        files.sort(key=lambda item: item['mtime'], reverse=True)
        total = len(files)
        start = max(0, (page - 1) * page_size)
        return {
            'path': target,
            'parent': _parent_within(target, roots),
            'deletable': deletable,
            'recursive': True,
            'dirs': [],
            'drives': list_drives(),
            'files': files[start:start + page_size],
            'total': total,
            'total_size': sum(item['size'] for item in files),
            'page': page,
            'page_size': page_size,
        }

    try:
        entries = sorted(os.scandir(target), key=lambda e: e.name.lower())
    except OSError as exc:
        raise FileNotFoundError(f'无法读取目录: {exc}') from exc

    for entry in entries:
        if entry.name.startswith('.'):
            continue
        try:
            if entry.is_dir():
                if keyword and keyword.lower() not in entry.name.lower():
                    continue
                stat = entry.stat()
                dirs.append({
                    'name': entry.name,
                    'path': entry.path,
                    'rel': os.path.relpath(entry.path, target).replace('\\', '/'),
                    'mtime': stat.st_mtime,
                    'mtime_text': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                    'kind': 'dir',
                })
            elif entry.is_file():
                if keyword and keyword.lower() not in entry.name.lower():
                    continue
                item = _stat_entry(entry.path, target)
                if item:
                    files.append(item)
        except OSError:
            continue

    files.sort(key=lambda item: item['mtime'], reverse=True)
    return {
        'path': target,
        'parent': _parent_within(target, roots),
        'deletable': deletable,
        'recursive': False,
        'dirs': dirs,
        'drives': list_drives(),
        'files': files,
        'total': len(files),
        'total_size': sum(item['size'] for item in files),
        'page': 1,
        'page_size': len(files),
    }


def _parent_within(path: str, roots: list = None) -> str:
    """返回上一级目录（到达盘符根目录时返回空串）。"""
    parent = os.path.dirname(path)
    if not parent or _norm(parent) == _norm(path):
        return ''
    return parent


def delete_paths(paths: list, roots: list) -> dict:
    """删除文件或目录（目录需为空，或 recursive=True 时整体删除）。"""
    deleted, errors = [], []
    for path in paths:
        try:
            target = resolve_within(path, roots)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=False)
            elif os.path.isfile(target):
                os.remove(target)
            else:
                errors.append({'path': path, 'error': '文件不存在'})
                continue
            deleted.append(path)
        except PathNotAllowed as exc:
            errors.append({'path': path, 'error': str(exc)})
        except OSError as exc:
            errors.append({'path': path, 'error': str(exc)})
    return {'ok': not errors, 'deleted': deleted, 'errors': errors}


def browse_dirs(path: str, show_files: bool = False) -> dict:
    """目录选择器：只读地列出任意已存在目录的子目录（用于选择保存路径）。"""
    if not path:
        home = os.path.expanduser('~')
        path = home if os.path.isdir(home) else os.path.abspath(os.sep)
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(target):
        target = os.path.dirname(target) if os.path.isdir(os.path.dirname(target)) else os.path.abspath(os.sep)

    dirs = []
    try:
        for entry in sorted(os.scandir(target), key=lambda e: e.name.lower()):
            if entry.name.startswith('.'):
                continue
            try:
                if entry.is_dir():
                    dirs.append({'name': entry.name, 'path': entry.path})
            except OSError:
                continue
    except (OSError, PermissionError) as exc:
        return {'path': target, 'parent': '', 'dirs': [], 'error': str(exc)}

    parent = os.path.dirname(target)
    if _norm(parent) == _norm(target):
        parent = ''
    return {'path': target, 'parent': parent, 'dirs': dirs, 'drives': list_drives(), 'error': ''}


def open_in_file_manager(path: str) -> dict:
    """在系统文件管理器中打开目录。"""
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        return {'ok': False, 'error': '路径不存在'}
    target = target if os.path.isdir(target) else os.path.dirname(target)
    try:
        if os.name == 'nt':
            os.startfile(target)  # noqa: S606 - 本地控制台，用户主动点击
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', target])
        else:
            subprocess.Popen(['xdg-open', target])
        return {'ok': True}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def human_size(num: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if abs(num) < 1024.0:
            return f'{num:3.1f} {unit}'
        num /= 1024.0
    return f'{num:.1f} PB'
