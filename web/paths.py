# -*- coding: utf-8 -*-

"""路径解析：项目根目录、配置文件、保存目录、日志目录。"""

import os
import sys

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(WEB_DIR)

CONFIG_REL = os.path.join('config', 'config.ini')
URL_CONFIG_REL = os.path.join('config', 'URL_config.ini')
LOG_DIR_REL = 'logs'
DEFAULT_SAVE_DIRNAME = 'downloads'

CONFIG_FILE = os.path.join(PROJECT_ROOT, CONFIG_REL)
URL_CONFIG_FILE = os.path.join(PROJECT_ROOT, URL_CONFIG_REL)
LOG_DIR = os.path.join(PROJECT_ROOT, LOG_DIR_REL)


def resolve_save_path(project_root: str = None) -> tuple:
    """返回 (录制保存目录, 来源说明)。

    优先使用 config.ini 中的「直播保存路径」，为空时使用项目下的 downloads 目录。
    目录不存在时取项目根目录，保证 shutil.disk_usage 可用。
    """
    root = project_root or PROJECT_ROOT
    configured = ''
    try:
        from config_store import read_config_values
        values = read_config_values(os.path.join(root, CONFIG_REL))
        configured = (values.get('录制设置', {}) or {}).get('直播保存路径(不填则默认)', '') or ''
    except Exception:
        configured = ''

    if configured.strip():
        path = os.path.expanduser(configured.strip())
        if not os.path.isabs(path):
            path = os.path.join(root, path)
        return os.path.normpath(path), 'config'
    return os.path.join(root, DEFAULT_SAVE_DIRNAME), 'default'


def default_save_path(project_root: str = None) -> str:
    return os.path.join(project_root or PROJECT_ROOT, DEFAULT_SAVE_DIRNAME)


def pick_python(project_root: str = None) -> str:
    """优先使用项目内的虚拟环境，其次使用当前解释器。"""
    root = project_root or PROJECT_ROOT
    if os.name == 'nt':
        candidates = [
            os.path.join(root, '.venv', 'Scripts', 'python.exe'),
            os.path.join(root, 'venv', 'Scripts', 'python.exe'),
        ]
    else:
        candidates = [
            os.path.join(root, '.venv', 'bin', 'python3'),
            os.path.join(root, '.venv', 'bin', 'python'),
            os.path.join(root, 'venv', 'bin', 'python3'),
            os.path.join(root, 'venv', 'bin', 'python'),
        ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return sys.executable
