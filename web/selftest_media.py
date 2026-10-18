# -*- coding: utf-8 -*-
"""
媒体后处理自检（合并 / 裁边转 16:9）

用法：
    python web/selftest_media.py              # 纯函数 + 真实 ffmpeg 集成测试
    python web/selftest_media.py --no-ffmpeg  # 只跑纯函数（不生成视频）

集成测试会在系统临时目录里生成几段小视频，验证：
* 合并后的时长/帧数与输入合计一致；
* 「转 16:9」优先走无损路径，且除 SPS 裁剪参数外视频码流一字节未变；
* 编码参数不一致时会明确拒绝，而不是悄悄压坏画面。
跑完自动清理临时文件，不会碰你的录制目录。
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

WEB = os.path.dirname(os.path.abspath(__file__))
if WEB not in sys.path:
    sys.path.insert(0, WEB)

import media_tools as mt  # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = ''):
    (PASS if condition else FAIL).append(name)
    print(f'  [{"OK " if condition else "FAIL"}] {name}' + (f' -> {detail}' if detail else ''))


# ---------------------------------------------------------------- 纯函数
def test_pure():
    print('== 纯函数 ==')
    names = ['a_10.mp4', 'a_2.mp4', 'a_1.mp4', 'b.mp4']
    ordered = sorted(names, key=mt.natural_key)
    check('自然排序 a_1 < a_2 < a_10', ordered == ['a_1.mp4', 'a_2.mp4', 'a_10.mp4', 'b.mp4'], str(ordered))

    check('even() 结果都是偶数', all(mt.even(v) % 2 == 0 for v in range(1, 2000)))
    check('even(1080) = 1080', mt.even(1080) == 1080)

    check('is_valid_16x9(1920,1080)', mt.is_valid_16x9(1920, 1080) is True)
    check('is_valid_16x9(1920,1810) 为假', mt.is_valid_16x9(1920, 1810) is False)
    check('is_valid_16x9(1280,720)', mt.is_valid_16x9(1280, 720) is True)

    # 兜底裁剪（用户强制允许切画面时用）必须始终裁出严格的 16:9
    fallback_ok = True
    fallback_detail = []
    for width, height in [(1920, 1810), (1920, 1080), (1280, 800), (1920, 1440), (640, 600)]:
        crop = mt.frame_16x9_crop(width, height)
        ratio = crop['width'] / crop['height']
        fits = (crop['width'] <= width and crop['height'] <= height
                and crop['x'] >= 0 and crop['y'] >= 0
                and crop['x'] + crop['width'] <= width
                and crop['y'] + crop['height'] <= height)
        if abs(ratio - 16 / 9) > 0.002 or not fits:
            fallback_ok = False
            fallback_detail.append(f'{width}x{height}->{crop}')
    check('兜底裁剪结果始终是严格 16:9 且不越界', fallback_ok, '; '.join(fallback_detail))

    # 压缩档位元数据
    presets = mt.presets_info()
    codec_ids = [c['id'] for c in presets['codecs']]
    check('压缩编码器含 h264 / av1', codec_ids == ['h264', 'av1'], str(codec_ids))
    level_ids = [l['id'] for l in presets['levels']]
    check('压缩强度三档', level_ids == ['light', 'medium', 'strong'], str(level_ids))
    ratios = [l['ratio'] for l in presets['levels']]
    check('强度依次减弱（ratio 递减）', ratios == sorted(ratios, reverse=True), str(ratios))
    check('每档都有说明', all(l.get('note') for l in presets['levels']))
    check('AV1 使用 preset<10（SVT 官方警告该档位不保证画质）',
          int(mt.CODEC_SETTINGS['av1']['preset']) < 10, str(mt.CODEC_SETTINGS['av1']['preset']))
    check('耗时预估都是正数',
          all(c['minutes_per_source_hour'] and c['minutes_per_source_hour'] > 0
              for c in presets['codecs']))
    check('AV1 预估耗时比 H.264 长',
          next(c for c in presets['codecs'] if c['id'] == 'av1')['minutes_per_source_hour']
          > next(c for c in presets['codecs'] if c['id'] == 'h264')['minutes_per_source_hour'])

    # 体积估算：按源码率打折（CRF 是按画质、不保证变小，所以不能用 CRF 承诺体积）
    # 构造一份自洽的数据：5 Mbps 视频 + 128 kbps 音频，100 秒 -> 64.1 MB
    src_total_bitrate = 5_000_000 + 128_000
    est_info = {'size': int(src_total_bitrate * 100 / 8), 'duration': 100.0,
                'audio': {'bit_rate': 128000}, 'video': {'bit_rate': 5_000_000}}
    est = mt.estimate_compress(est_info, 'medium')
    check('估算目标码率 = 源码率 × 0.5', est['target_video_bitrate'] == 2_500_000,
          str(est['target_video_bitrate']))
    check('估算体积含音频', est['estimated_size'] == int((2_500_000 + 128_000) * 100 / 8),
          str(est['estimated_size']))
    expected_ratio = (2_500_000 + 128_000) / src_total_bitrate
    check('估算比例 ≈ 目标码率占比', abs(est['estimated_ratio'] - expected_ratio) < 0.005,
          f"{est['estimated_ratio']} vs {expected_ratio:.4f}")
    fallback = mt.estimate_compress(
        {'size': 100_000_000, 'duration': 100.0, 'audio': {'bit_rate': 128000},
         'video': {'bit_rate': 0}}, 'medium')
    check('缺少 video.bit_rate 时按总大小推算',
          fallback['ok'] and fallback['source_video_bitrate'] > 0,
          str(fallback.get('source_video_bitrate')))

    # 1920x1810、内容占顶部 1078 行 —— 与真实案例一致的场景
    info = {'path': 'x', 'name': 'x.mp4', 'size': 1, 'mtime': 0, 'duration': 10,
            'video': {'codec': 'h264', 'width': 1920, 'height': 1810, 'pix_fmt': 'yuv420p',
                      'fps': 60.0, 'avg_fps': 60.0, 'sar': '1:1', 'dar': '192:181',
                      'nb_frames': 600, 'bit_rate': 1, 'profile': 'High'},
            'audio': {'codec': 'aac', 'sample_rate': 48000, 'channels': 2, 'bit_rate': 128000}}
    box = {'ok': True, 'width': 1918, 'height': 1078, 'x': 0, 'y': 0, 'samples': [], 'reason': ''}
    plan = mt.plan_to16x9(info, box)
    check('底部黑边 -> action=crop', plan.get('action') == 'crop', str(plan.get('action')))
    check('底部黑边 -> 走无损 sps', plan.get('mode') == 'sps', str(plan.get('mode')))
    check('底部黑边 -> 目标高度 1080', plan.get('target_height') == 1080, str(plan.get('target_height')))
    check('底部黑边 -> 裁 730 行', plan.get('removed_rows') == 730, str(plan.get('removed_rows')))
    check('底部黑边 -> 不会切画面', plan.get('lost_rows') == 0, str(plan.get('lost_rows')))
    check('SPS 裁剪量 = 1824-1080 = 744', mt._align16(1810) - plan['target_height'] == 744,
          str(mt._align16(1810) - plan['target_height']))

    # 已经是 16:9
    info169 = dict(info, video=dict(info['video'], height=1080, dar='16:9'))
    box169 = {'ok': True, 'width': 1918, 'height': 1078, 'x': 0, 'y': 0, 'samples': [], 'reason': ''}
    check('已 16:9 -> action=none', mt.plan_to16x9(info169, box169).get('action') == 'none')

    # 内容比 16:9 高得多，裁切会切掉大量画面 -> 应 blocked
    box_tall = {'ok': True, 'width': 1918, 'height': 1600, 'x': 0, 'y': 0, 'samples': [], 'reason': ''}
    check('内容过高 -> action=blocked', mt.plan_to16x9(info, box_tall).get('action') == 'blocked')

    # 左右黑边（竖屏塞进 16:9 画布）
    info_wide = dict(info, video=dict(info['video'], width=1920, height=1080))
    box_pillar = {'ok': True, 'width': 608, 'height': 1080, 'x': 656, 'y': 0, 'samples': [], 'reason': ''}
    plan_pillar = mt.plan_to16x9(info_wide, box_pillar)
    check('左右黑边 -> action=crop', plan_pillar.get('action') == 'crop', str(plan_pillar.get('action')))
    check('左右黑边 -> 必须重编码', plan_pillar.get('mode') == 'reencode', str(plan_pillar.get('mode')))

    # 合并兼容性
    same = [dict(info), dict(info)]
    check('同参数 -> 可无损合并', mt.check_compat(same).get('ok') is True)
    diff = [dict(info), dict(info, video=dict(info['video'], width=1280, height=720))]
    compat = mt.check_compat(diff)
    check('分辨率不同 -> 拒绝合并', compat.get('ok') is False)
    check('  拒绝原因可读', any('分辨率' in p for p in compat.get('problems', [])), str(compat.get('problems'))[:80])

    # 输出名派生 + 避免覆盖
    tmp = tempfile.mkdtemp(prefix='dlr_name_')
    try:
        src = os.path.join(tmp, '主播_2026-01-01_00-00-00_000.mp4')
        open(src, 'wb').close()
        first = mt.derive_output_path([src], '合并')
        check('派生名去掉分段序号', os.path.basename(first) == '主播_2026-01-01_00-00-00_合并.mp4',
              os.path.basename(first))
        open(first, 'wb').close()
        second = mt.derive_output_path([src], '合并')
        check('重名时自动加序号', os.path.basename(second) == '主播_2026-01-01_00-00-00_合并 (2).mp4',
              os.path.basename(second))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 集成
def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')


def _make_clip(ffmpeg, out_path, width, height, content_h, seconds=2, frequency=440):
    """生成「顶部 content_h 行有画面、其余纯黑」的视频。"""
    cmd = [
        ffmpeg, '-hide_banner', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', f'testsrc2=s={width}x{content_h}:r=30:d={seconds}',
        '-f', 'lavfi', '-i', f'color=black:s={width}x{height}:r=30:d={seconds}',
        '-f', 'lavfi', '-i', f'sine=f={frequency}:d={seconds}',
        '-filter_complex', '[1:v][0:v]overlay=0:0[v]',
        '-map', '[v]', '-map', '2:a',
        '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-shortest', out_path,
    ]
    return _run(cmd)


def _video_hash(ffmpeg, path, drop_sps=True):
    args = [ffmpeg, '-hide_banner', '-v', 'error', '-i', path, '-map', '0:v:0', '-c', 'copy']
    if drop_sps:
        args += ['-bsf:v', 'filter_units=remove_types=7']
    args += ['-f', 'hash', '-hash', 'md5', '-']
    result = _run(args)
    for line in (result.stdout or '').splitlines():
        if 'MD5=' in line:
            return line.split('MD5=')[1].strip()
    return ''


def test_integration():
    print('== 集成（真实 ffmpeg）==')
    try:
        ffmpeg = mt.find_ffmpeg()
        mt.find_ffprobe()
    except mt.MediaError as exc:
        print(f'    [跳过] {exc}')
        return

    tmp = tempfile.mkdtemp(prefix='dlr_media_selftest_')
    try:
        # --- 无损转 16:9
        tall = os.path.join(tmp, 'tall.mp4')
        result = _make_clip(ffmpeg, tall, 640, 600, 360)
        if result.returncode != 0:
            check('生成测试素材', False, (result.stderr or '')[-200:])
            return
        check('生成 640x600（内容 360 行）素材', True)

        info = mt.probe(tall)
        box = mt.detect_content_box(tall, info['duration'], samples=3)
        check('cropdetect 找到内容框', box.get('ok') and box.get('height') == 360, str(box.get('height')))

        before = _video_hash(ffmpeg, tall)
        converted = mt.to_16x9(tall)
        out_info = mt.probe(converted['output'])
        check('输出为 640x360', (out_info['video']['width'], out_info['video']['height']) == (640, 360),
              f"{out_info['video']['width']}x{out_info['video']['height']}")
        check('走的是无损路径', converted.get('lossless') is True, str(converted.get('mode')))
        check('时长基本不变',
              abs(out_info['duration'] - info['duration']) < 0.1,
              f"{out_info['duration']} vs {info['duration']}")
        after = _video_hash(ffmpeg, converted['output'])
        check('除 SPS 外视频码流完全一致（无损证明）', bool(before) and before == after,
              f'{before[:12]} / {after[:12]}')
        check('音轨仍在', out_info.get('audio') is not None, str(out_info.get('audio')))

        # --- 已经是 16:9 的文件应被拒绝
        flat = os.path.join(tmp, 'flat.mp4')
        _make_clip(ffmpeg, flat, 640, 360, 360)
        try:
            mt.to_16x9(flat)
            check('已 16:9 的文件被拒绝处理', False, '没有抛错')
        except mt.MediaError as exc:
            check('已 16:9 的文件被拒绝处理', '16:9' in str(exc), str(exc)[:60])

        # --- 合并
        clips = []
        for index in range(3):
            path = os.path.join(tmp, f'part_{index}.mp4')
            _make_clip(ffmpeg, path, 640, 360, 360, frequency=300 + index * 50)
            clips.append(path)
        expected_duration = sum(mt.probe(c)['duration'] for c in clips)
        expected_frames = sum(mt.probe(c)['video']['nb_frames'] for c in clips)
        merged = mt.merge(clips)
        merged_info = mt.probe(merged['output'])
        check('合并后时长 = 输入合计',
              abs(merged_info['duration'] - expected_duration) < 0.3,
              f"{merged_info['duration']} vs {expected_duration}")
        if expected_frames:
            check('合并后帧数 = 输入合计',
                  merged_info['video']['nb_frames'] == expected_frames,
                  f"{merged_info['video']['nb_frames']} vs {expected_frames}")
        check('合并标记为无损', merged.get('lossless') is True)

        # --- 参数不一致必须拒绝
        odd = os.path.join(tmp, 'odd.mp4')
        _make_clip(ffmpeg, odd, 480, 270, 270, seconds=1)
        try:
            mt.prepare_merge([clips[0], odd])
            check('参数不一致被拒绝', False, '没有抛错')
        except mt.MediaError as exc:
            check('参数不一致被拒绝', '分辨率' in str(exc), str(exc)[:70])

        # --- 单个文件不能合并
        try:
            mt.prepare_merge([clips[0]])
            check('单文件被拒绝合并', False, '没有抛错')
        except mt.MediaError as exc:
            check('单文件被拒绝合并', '2' in str(exc), str(exc)[:50])

        # --- 压缩转码（H.264 / AV1）
        for codec, level in (('h264', 'medium'), ('av1', 'strong')):
            if codec == 'av1' and not mt.is_av1_supported():
                print('    [跳过] 当前 ffmpeg 不支持 AV1')
                continue
            small = os.path.join(tmp, f'cmp_{codec}.mp4')
            # 用稍大/稍长的素材：2 秒的极小片段码率控制来不及收敛，预估会偏得离谱
            made = _make_clip(ffmpeg, small, 640, 360, 360, seconds=4)
            if made.returncode != 0:
                check(f'压缩({codec}) 生成素材', False, (made.stderr or '')[-150:])
                continue
            src_info = mt.probe(small)
            est = mt.estimate_compress(src_info, level)
            result = mt.compress(small, codec=codec, level=level, crop_to_16x9=True)
            out_info = mt.probe(result['output'])
            expect = 'av1' if codec == 'av1' else 'h264'
            check(f'压缩({codec}) 输出编码正确', out_info['video']['codec'] == expect,
                  out_info['video']['codec'])
            check(f'压缩({codec}) 分辨率不变（无黑边时不裁）',
                  (out_info['video']['width'], out_info['video']['height']) == (640, 360),
                  f"{out_info['video']['width']}x{out_info['video']['height']}")
            check(f'压缩({codec}) 音轨保留', out_info.get('audio') is not None,
                  str(out_info.get('audio')))
            check(f'压缩({codec}) 体积确实变小', result['saved_ratio'] > 0,
                  f"src={result['source_size']} out={result['size']}")
            check(f'压缩({codec}) 结果含目标码率与强度',
                  result.get('target_video_bitrate') and result.get('level') == level,
                  str(result.get('target_video_bitrate')))
            # 预估精度：H.264 的 ABR 收敛快；AV1 在短片段上容易超出目标，放宽到 1 倍
            if est.get('ok') and est.get('estimated_size'):
                delta = abs(result['size'] - est['estimated_size']) / est['estimated_size']
                limit = 0.35 if codec == 'h264' else 1.0
                check(f'压缩({codec}) 预估体积与实际接近', delta < limit,
                      f'偏差 {delta*100:.0f}%（上限 {limit*100:.0f}%）')

        # --- 非法编码器 / 强度必须拒绝
        for bad in ({'codec': 'vp9'}, {'codec': 'h264', 'level': 'ultra'}):
            try:
                mt.compress(clips[0], **bad)
                check(f'非法参数 {bad} 被拒绝', False, '没有抛错')
            except mt.MediaError as exc:
                check(f'非法参数 {bad} 被拒绝', '不支持' in str(exc), str(exc)[:50])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-ffmpeg', action='store_true', help='只跑纯函数检查')
    args = parser.parse_args()

    test_pure()
    if not args.no_ffmpeg:
        test_integration()

    print('\n' + '=' * 60)
    print(f'通过 {len(PASS)} 项，失败 {len(FAIL)} 项')
    if FAIL:
        for name in FAIL:
            print('  -', name)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
