# -*- coding: utf-8 -*-

"""
录制结束后的自动后处理：裁黑边转 16:9 / 压缩。

为什么单独成一个模块：`main.py` 一被 import 就会读配置、检测 ffmpeg、进入主流程，
没法在测试里跑。把「结束确认 + 排队 + 调用 media_tools」抽出来，决策逻辑就能单独测。

**结束确认**是这个模块的核心，目的是两件事：
1. 别少录了——断流重连时上一段只是被切碎了，不能当成「真的录完」去处理；
2. 别处理半成品——必须确认文件已经写完、句柄已释放。

所以一段录制结束后会走这几道检查：
    进程退出
      → 等 delay_seconds（断流重连通常发生在这个窗口内）
      → 同一主播是否又开始录制了？是 → 判定重连，跳过
      → 文件体积连续多次采样不变？否 → 说明还在写，跳过
      → 文件是否小于 min_size_mb？是 → 碎片，跳过
      → 才真正开始处理（且以低优先级运行，避免和录播抢 CPU）
"""

import os
import queue
import sys
import threading
import time

from src.utils import logger

# 处理方式
MODE_CROP_ONLY = 'crop169'     # 只做无损裁边，体积不变
MODE_COMPRESS = 'compress'     # 重编码压缩（顺带裁边），推荐
MODE_BOTH = 'both'             # 先无损裁边留档，再压缩裁边后的文件

DEFAULT_CONFIG = {
    'enabled': False,
    'mode': MODE_COMPRESS,
    'codec': 'h264',
    'level': 'medium',
    'delay_seconds': 120,
    'min_size_mb': 50.0,
    'stable_checks': 3,
    'stable_interval': 2.0,
    'stable_attempts': 5,
}

# 网页下拉里存的是中文，这里映射成内部值
MODE_MAP = {
    '仅无损裁边转16:9': MODE_CROP_ONLY,
    '压缩(含裁边)': MODE_COMPRESS,
    '先无损裁边再压缩': MODE_BOTH,
}
CODEC_MAP = {'H.264': 'h264', 'AV1': 'av1'}
LEVEL_MAP = {'轻度(70%)': 'light', '中等(50%)': 'medium', '强力(30%)': 'strong'}


def parse_config(enabled: bool, mode: str, codec: str, level: str,
                 delay_seconds: int, min_size_mb: float) -> dict:
    """把配置里的中文选项翻译成内部值，非法值一律回退到安全默认。"""
    config = dict(DEFAULT_CONFIG)
    config['enabled'] = bool(enabled)
    config['mode'] = MODE_MAP.get((mode or '').strip(), MODE_COMPRESS)
    config['codec'] = CODEC_MAP.get((codec or '').strip().upper().replace('H264', 'H.264'), 'h264')
    config['level'] = LEVEL_MAP.get((level or '').strip(), 'medium')
    try:
        config['delay_seconds'] = max(0, int(delay_seconds))
    except (TypeError, ValueError):
        pass
    try:
        config['min_size_mb'] = max(0.0, float(min_size_mb))
    except (TypeError, ValueError):
        pass
    return config


def is_recording_again(record_name: str, snapshot) -> bool:
    """同一主播是否又开始录制了（说明刚才只是断流重连）。"""
    if not record_name or snapshot is None:
        return False
    try:
        return record_name in (snapshot() or ())
    except Exception:  # noqa: BLE001 - 快照函数出问题不应该挡住后处理
        return False


def wait_until_stable(path: str, checks: int = 3, interval: float = 2.0,
                      size_func=os.path.getsize, sleep=time.sleep) -> tuple:
    """文件体积连续 checks 次采样不变，才认为真的写完了。

    返回 (是否稳定, 原因)。file 不存在/为空/仍在增长都算不稳定。
    """
    sizes = []
    for index in range(max(1, int(checks))):
        if index:
            sleep(interval)
        try:
            sizes.append(size_func(path))
        except OSError as exc:
            return False, f'无法读取文件: {exc}'
    if sizes[-1] <= 0:
        return False, '文件为空'
    if len(set(sizes)) != 1:
        return False, f'文件体积仍在变化（采样: {sizes}）'
    return True, ''


def resolve_video_path(file_path: str) -> str:
    """录制产物可能还是 TS，转 mp4 是另一个线程做的；优先用同名 mp4。"""
    stem, ext = os.path.splitext(file_path)
    if ext.lower() == '.mp4':
        return file_path
    candidate = stem + '.mp4'
    if os.path.exists(candidate):
        return candidate
    return file_path


def _load_media_tools():
    """延迟导入 web/media_tools.py。

    放在函数里是因为：① 上游用法（没有 web 目录）不该因此起不来；
    ② main.py 启动时不需要为没开启的功能付导入成本。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_dir = os.path.join(project_root, 'web')
    if not os.path.isdir(web_dir):
        raise RuntimeError('找不到 web 目录，自动后处理需要 web/media_tools.py')
    if web_dir not in sys.path:
        sys.path.insert(0, web_dir)
    import media_tools  # noqa: PLC0415 - 故意延迟导入
    return media_tools


class PostProcessQueue:
    """串行执行的后处理队列。

    串行而不是并发：压缩本来就吃满 CPU，同时跑多个只会拖慢正在录制的进程，
    这正是用户担心的「别少录了」。
    """

    def __init__(self, config: dict, recording_snapshot=None, project_root: str = None,
                 media_loader=_load_media_tools):
        self.config = dict(DEFAULT_CONFIG, **(config or {}))
        self._snapshot = recording_snapshot
        self.project_root = project_root
        self._media_loader = media_loader
        self._media = None
        self._queue = queue.Queue()
        self._thread = None
        self._lock = threading.RLock()
        self._busy = threading.Event()

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._loop, name='auto-post-process', daemon=True)
            self._thread.start()

    def enqueue(self, record_name: str, file_path: str) -> None:
        """录制结束后调用。真正的检查都在后台做，不阻塞录制主循环。"""
        if not self.config.get('enabled') or not file_path:
            return
        self.start()
        self._queue.put((record_name, file_path))
        logger.info(f'[自动处理] 已加入队列：{os.path.basename(file_path)}'
                    f'（{self.config["delay_seconds"]} 秒后确认录制是否真的结束）')

    def pending(self) -> int:
        return self._queue.qsize()

    def wait_idle(self, timeout: float = 60.0) -> bool:
        """等到队列跑空且当前没有任务在处理（测试 / 优雅退出用）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._queue.qsize() == 0 and not self._busy.is_set():
                return True
            time.sleep(0.05)
        return False

    # ------------------------------------------------------------ 后台
    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            self._busy.set()
            try:
                self._handle(*item)
            except Exception as exc:  # noqa: BLE001 - 队列线程不能死
                logger.error(f'[自动处理] 处理 {item[1]} 时出错: {type(exc).__name__}: {exc}')
            finally:
                self._busy.clear()
                self._queue.task_done()

    def _handle(self, record_name: str, file_path: str) -> None:
        config = self.config
        name = os.path.basename(file_path)

        delay = int(config.get('delay_seconds') or 0)
        if delay > 0:
            time.sleep(delay)

        # 1) 断流重连：同一主播又开始录了，说明刚才那段只是被切碎，不要处理
        if is_recording_again(record_name, self._snapshot):
            logger.info(f'[自动处理] {record_name} 已重新开始录制，判定为断流重连，跳过处理 {name}')
            return

        target = resolve_video_path(file_path)

        # 2) 等文件写完（可能还在由 TS 转 mp4）
        stable = False
        reason = ''
        for attempt in range(int(config.get('stable_attempts') or 1)):
            stable, reason = wait_until_stable(
                target,
                checks=int(config.get('stable_checks') or 3),
                interval=float(config.get('stable_interval') or 2.0))
            if stable:
                break
            if attempt < int(config.get('stable_attempts') or 1) - 1:
                time.sleep(5)
        if not stable:
            logger.warning(f'[自动处理] 跳过 {os.path.basename(target)}：{reason}')
            return

        # 3) 太小的是碎片，没必要花时间
        try:
            size_mb = os.path.getsize(target) / 1024 / 1024
        except OSError as exc:
            logger.warning(f'[自动处理] 跳过 {target}：{exc}')
            return
        if size_mb < float(config.get('min_size_mb') or 0):
            logger.info(f'[自动处理] 跳过 {os.path.basename(target)}：'
                        f'体积 {size_mb:.1f} MB 小于阈值 {config["min_size_mb"]} MB')
            return

        self._run_steps(record_name, target, size_mb)

    def _run_steps(self, record_name: str, file_path: str, size_mb: float) -> None:
        media = self._get_media()
        config = self.config
        mode = config.get('mode')
        name = os.path.basename(file_path)
        logger.info(f'[自动处理] 开始处理 {name}（{size_mb:.1f} MB，方式={mode}）')

        current = file_path

        if mode in (MODE_CROP_ONLY, MODE_BOTH):
            try:
                result = media.to_16x9(current, project_root=self.project_root,
                                       prefer_lossless=True)
                logger.info(f'[自动处理] 无损裁边完成：{result["name"]}'
                            f'（{result["size"] / 1e6:.1f} MB，{"无损" if result["lossless"] else "重编码"}）')
                if mode == MODE_CROP_ONLY:
                    return
                current = result['output']
            except media.MediaError as exc:
                logger.info(f'[自动处理] 跳过无损裁边：{exc}')
                if mode == MODE_CROP_ONLY:
                    return

        if mode in (MODE_COMPRESS, MODE_BOTH):
            try:
                result = media.compress(
                    current, project_root=self.project_root,
                    codec=config.get('codec') or 'h264',
                    level=config.get('level') or 'medium',
                    crop_to_16x9=(mode == MODE_COMPRESS),
                    low_priority=True)
                logger.info(f'[自动处理] 压缩完成：{result["name"]}  '
                            f'{result["source_size"] / 1e6:.1f} MB -> {result["size"] / 1e6:.1f} MB'
                            f'（省 {result["saved_ratio"] * 100:.0f}%）')
            except media.MediaError as exc:
                logger.error(f'[自动处理] 压缩失败：{exc}')

    def _get_media(self):
        with self._lock:
            if self._media is None:
                self._media = self._media_loader()
            return self._media
