# -*- coding: utf-8 -*-
"""
录制结束后自动后处理的自检。

用法：
    python web/selftest_post_process.py

重点验证「别少录了」的那部分逻辑：
* 断流重连（同一主播又开始录）不能当成录制结束去处理；
* 文件还在写（体积变化）不能处理；
* 太小的碎片不能处理；
* 三种处理方式的分派正确（仅裁边 / 压缩 / 先裁边再压缩）。

不需要 ffmpeg，也不会碰真实录像——媒体模块用假的替身。
"""

import os
import shutil
import sys
import tempfile
import threading
import time

WEB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WEB)
for path in (ROOT, WEB):
    if path not in sys.path:
        sys.path.insert(0, path)

from src import post_process as pp  # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = ''):
    (PASS if condition else FAIL).append(name)
    print(f'  [{"OK " if condition else "FAIL"}] {name}' + (f' -> {detail}' if detail else ''))


# ---------------------------------------------------------------- 假的媒体模块
class FakeMediaError(Exception):
    pass


class FakeMedia:
    """替身：只记录被调用了什么，不真的编码。"""

    MediaError = FakeMediaError

    def __init__(self):
        self.calls = []

    def to_16x9(self, path, project_root=None, prefer_lossless=True, **kwargs):
        self.calls.append({'fn': 'to_16x9', 'path': path})
        return {'output': path + '.169', 'name': os.path.basename(path) + '.169',
                'size': 1, 'lossless': True}

    def compress(self, path, project_root=None, codec='h264', level='medium',
                 crop_to_16x9=True, low_priority=False, **kwargs):
        self.calls.append({'fn': 'compress', 'path': path, 'codec': codec,
                           'crop_to_16x9': crop_to_16x9, 'low_priority': low_priority})
        return {'output': path + '.cmp', 'name': os.path.basename(path) + '.cmp',
                'size': 1, 'source_size': 2, 'saved_ratio': 0.5}


def make_file(directory, name, size=200 * 1024 * 1024):
    path = os.path.join(directory, name)
    with open(path, 'wb') as fp:
        fp.write(b'\0' * size)
    return path


# ---------------------------------------------------------------- 纯函数
def test_parse_config():
    print('== parse_config ==')
    cfg = pp.parse_config(True, '压缩(含裁边)', 'AV1', '强力(30%)', 90, 30)
    check('方式映射正确', cfg['mode'] == pp.MODE_COMPRESS, cfg['mode'])
    check('编码器映射正确', cfg['codec'] == 'av1', cfg['codec'])
    check('强度映射正确', cfg['level'] == 'strong', cfg['level'])
    check('等待秒数', cfg['delay_seconds'] == 90, str(cfg['delay_seconds']))
    check('最小文件 MB', cfg['min_size_mb'] == 30.0, str(cfg['min_size_mb']))

    check('仅裁边方式', pp.parse_config(True, '仅无损裁边转16:9', 'H.264', '轻度(70%)', 0, 0)['mode']
          == pp.MODE_CROP_ONLY)
    check('先裁边再压缩方式', pp.parse_config(True, '先无损裁边再压缩', 'H.264', '轻度(70%)', 0, 0)['mode']
          == pp.MODE_BOTH)

    fallback = pp.parse_config(True, '瞎写的', 'VP9', '超级强', -5, -1)
    check('非法方式回退默认', fallback['mode'] == pp.MODE_COMPRESS, fallback['mode'])
    check('非法编码器回退 h264', fallback['codec'] == 'h264', fallback['codec'])
    check('非法强度回退 medium', fallback['level'] == 'medium', fallback['level'])
    check('负数等待被夹到 0', fallback['delay_seconds'] == 0, str(fallback['delay_seconds']))
    check('负数最小体积被夹到 0', fallback['min_size_mb'] == 0.0, str(fallback['min_size_mb']))

    check('关闭时 enabled=False', pp.parse_config(False, '', '', '', 1, 1)['enabled'] is False)


def test_is_recording_again():
    print('== is_recording_again ==')
    check('在录制集合里 -> True', pp.is_recording_again('主播A', lambda: {'主播A'}) is True)
    check('不在集合里 -> False', pp.is_recording_again('主播A', lambda: {'主播B'}) is False)
    check('空名字 -> False', pp.is_recording_again('', lambda: {'主播A'}) is False)
    check('快照为 None -> False', pp.is_recording_again('主播A', None) is False)

    def boom():
        raise RuntimeError('快照炸了')

    check('快照抛异常 -> False（不挡后处理）', pp.is_recording_again('主播A', boom) is False)


def test_wait_until_stable():
    print('== wait_until_stable ==')
    sizes_stable = iter([100, 100, 100, 100])
    ok, reason = pp.wait_until_stable('x', checks=3, interval=0,
                                      size_func=lambda _p: next(sizes_stable), sleep=lambda _s: None)
    check('体积不变 -> 稳定', ok is True, reason)

    sizes_grow = iter([100, 200, 300])
    ok, reason = pp.wait_until_stable('x', checks=3, interval=0,
                                      size_func=lambda _p: next(sizes_grow), sleep=lambda _s: None)
    check('体积在变 -> 不稳定', ok is False, reason)
    check('  原因里提到体积变化', '变化' in reason, reason)

    ok, reason = pp.wait_until_stable('x', checks=3, interval=0,
                                      size_func=lambda _p: 0, sleep=lambda _s: None)
    check('空文件 -> 不稳定', ok is False, reason)

    def missing(_p):
        raise OSError('文件不存在')

    ok, reason = pp.wait_until_stable('x', checks=2, interval=0,
                                      size_func=missing, sleep=lambda _s: None)
    check('读不到文件 -> 不稳定', ok is False, reason)


def test_resolve_video_path():
    print('== resolve_video_path ==')
    tmp = tempfile.mkdtemp(prefix='pp_resolve_')
    try:
        ts = make_file(tmp, 'a.ts', 10)
        make_file(tmp, 'a.mp4', 10)
        check('有同名 mp4 时优先用 mp4', pp.resolve_video_path(ts).endswith('a.mp4'),
              pp.resolve_video_path(ts))
        only_ts = make_file(tmp, 'b.ts', 10)
        check('没有 mp4 时用原文件', pp.resolve_video_path(only_ts).endswith('b.ts'))
        mp4 = make_file(tmp, 'c.mp4', 10)
        check('本身就是 mp4 时原样返回', pp.resolve_video_path(mp4) == mp4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 队列行为
def run_queue(config, record_name, file_path, snapshot=None, timeout=20):
    media = FakeMedia()
    queue = pp.PostProcessQueue(config, recording_snapshot=snapshot,
                                media_loader=lambda: media)
    queue.enqueue(record_name, file_path)
    queue.wait_idle(timeout)
    return media


FAST = {'stable_checks': 1, 'stable_interval': 0, 'stable_attempts': 1}


def test_queue_dispatch():
    print('== 队列：处理方式分派 ==')
    tmp = tempfile.mkdtemp(prefix='pp_queue_')
    try:
        # 仅无损裁边
        f1 = make_file(tmp, 'crop.mp4')
        media = run_queue(dict(pp.DEFAULT_CONFIG, enabled=True, mode=pp.MODE_CROP_ONLY,
                               delay_seconds=0, min_size_mb=1, **FAST), '主播A', f1)
        check('仅裁边 -> 只调 to_16x9',
              [c['fn'] for c in media.calls] == ['to_16x9'], str(media.calls))

        # 压缩（含裁边）
        f2 = make_file(tmp, 'compress.mp4')
        media = run_queue(dict(pp.DEFAULT_CONFIG, enabled=True, mode=pp.MODE_COMPRESS,
                               delay_seconds=0, min_size_mb=1, **FAST), '主播A', f2)
        check('压缩 -> 只调 compress', [c['fn'] for c in media.calls] == ['compress'], str(media.calls))
        check('  压缩时带裁边', media.calls and media.calls[0]['crop_to_16x9'] is True)
        check('  压缩用低优先级（别和录制抢 CPU）',
              media.calls and media.calls[0]['low_priority'] is True)

        # 先裁边再压缩：第二步必须作用于裁边产物，且不再重复裁
        f3 = make_file(tmp, 'both.mp4')
        media = run_queue(dict(pp.DEFAULT_CONFIG, enabled=True, mode=pp.MODE_BOTH,
                               delay_seconds=0, min_size_mb=1, **FAST), '主播A', f3)
        check('先裁边再压缩 -> 两个步骤都执行',
              [c['fn'] for c in media.calls] == ['to_16x9', 'compress'], str(media.calls))
        if len(media.calls) == 2:
            check('  压缩作用于裁边后的文件', media.calls[1]['path'] == f3 + '.169',
                  media.calls[1]['path'])
            check('  第二步不再重复裁边', media.calls[1]['crop_to_16x9'] is False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_queue_guards():
    print('== 队列：结束确认（别少录了）==')
    tmp = tempfile.mkdtemp(prefix='pp_guard_')
    try:
        base = dict(pp.DEFAULT_CONFIG, enabled=True, mode=pp.MODE_COMPRESS,
                    delay_seconds=0, min_size_mb=1, **FAST)

        # 断流重连：同一主播又在录 -> 跳过
        f1 = make_file(tmp, 'reconnect.mp4')
        media = run_queue(base, '主播A', f1, snapshot=lambda: {'主播A'})
        check('断流重连 -> 不处理', media.calls == [], str(media.calls))

        # 已经不在录制 -> 正常处理
        f2 = make_file(tmp, 'finished.mp4')
        media = run_queue(base, '主播A', f2, snapshot=lambda: set())
        check('确实录完 -> 处理', [c['fn'] for c in media.calls] == ['compress'], str(media.calls))

        # 碎片太小 -> 跳过
        f3 = make_file(tmp, 'tiny.mp4', size=1024)
        media = run_queue(dict(base, min_size_mb=50), '主播A', f3)
        check('小于最小体积 -> 跳过', media.calls == [], str(media.calls))

        # 功能关闭时 enqueue 不做事
        queue = pp.PostProcessQueue(dict(pp.DEFAULT_CONFIG, enabled=False), media_loader=FakeMedia)
        queue.enqueue('主播A', f2)
        check('功能关闭 -> 不入队', queue.pending() == 0, str(queue.pending()))

        # 文件不存在 -> 不崩，只是跳过
        missing = os.path.join(tmp, 'nope.mp4')
        media = run_queue(base, '主播A', missing)
        check('文件不存在 -> 安全跳过', media.calls == [], str(media.calls))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_queue_serialization():
    print('== 队列：串行执行 ==')
    tmp = tempfile.mkdtemp(prefix='pp_serial_')
    try:
        base = dict(pp.DEFAULT_CONFIG, enabled=True, mode=pp.MODE_COMPRESS,
                    delay_seconds=0, min_size_mb=1, **FAST)
        media = FakeMedia()

        def worker_count():
            return len([t for t in threading.enumerate() if t.name == 'auto-post-process'])

        before = worker_count()
        queue = pp.PostProcessQueue(base, media_loader=lambda: media)
        for index in range(3):
            queue.enqueue('主播A', make_file(tmp, f's{index}.mp4'))
        # 反复 enqueue 也只应该有一个 worker（每次 enqueue 都会调 start）
        queue.enqueue('主播A', make_file(tmp, 's3.mp4'))
        queue.wait_idle(30)
        after = worker_count()
        check('四个任务都跑了', len(media.calls) == 4, str(len(media.calls)))
        check('只创建一个 worker 线程', after - before == 1, f'{before} -> {after}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_parse_config()
    test_is_recording_again()
    test_wait_until_stable()
    test_resolve_video_path()
    test_queue_dispatch()
    test_queue_guards()
    test_queue_serialization()

    print('\n' + '=' * 60)
    print(f'通过 {len(PASS)} 项，失败 {len(FAIL)} 项')
    if FAIL:
        for name in FAIL:
            print('  -', name)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
