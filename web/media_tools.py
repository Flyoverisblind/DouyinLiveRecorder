# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 录制文件后处理

两件事，都优先走「不重新编码」的路线：

1. **多段合并**：concat demuxer + stream copy，音视频码流原样拼接，
   前提是各段编码参数一致（不一致会明确报出差异，而不是悄悄压坏画面）；
2. **裁掉黑边转 16:9**：改写 H.264 SPS 的 frame cropping 参数
   （只改码流头里「可见区域」的声明，像素一个字节都没动），
   遇到 H.264 以外、或需要裁掉左右黑边时必须重编码的情况，才退回 libx264。

为什么值得这么做：一个 3 小时 1080p60 的录像重编码要几个小时且有代际损失，
而上面两条路通常几十秒就能完成，且画质/帧率/音轨与原片完全一致。

所有耗时操作都通过 job 对象回调进度并响应取消（见 media_jobs.py）。
"""

import json
import os
import re
import shutil
import subprocess
import time

# ---------------------------------------------------------------- 常量与异常

DEFAULT_CRF = 16
DEFAULT_PRESET = 'superfast'
SAMPLE_SECONDS = 2.0          # cropdetect 每次采样的解码时长
RECENT_WRITE_SECONDS = 120    # 修改时间在这么多秒内，认为可能仍在录制

_CROP_RE = re.compile(r'crop=(\d+):(\d+):(\d+):(\d+)')
_NAT_RE = re.compile(r'(\d+)')
_BIN_CACHE = {}
# 探测结果缓存：键里带上 size+mtime，文件一被改动就自动失效，
# 这样「先分析、再执行」时不必把同一个 8GB 文件解析两遍。
_CACHE = {}
_CACHE_MAX = 256


def _cache_key(path: str, extra: str = ''):
    try:
        stat = os.stat(path)
        return (os.path.abspath(path), stat.st_size, int(stat.st_mtime), extra)
    except OSError:
        return None


def _cache_get(key):
    return _CACHE.get(key) if key else None


def _cache_put(key, value):
    if not key:
        return value
    if len(_CACHE) >= _CACHE_MAX:
        for old in list(_CACHE)[: _CACHE_MAX // 4]:
            _CACHE.pop(old, None)
    _CACHE[key] = value
    return value



class MediaError(Exception):
    """可预期的失败（参数 / 环境 / 文件问题），接口层会转成 400。"""


class Cancelled(Exception):
    """任务被用户取消。"""


def natural_key(name: str) -> list:
    """把 'a_2.mp4' 排在 'a_10.mp4' 前面。"""
    return [int(part) if part.isdigit() else part.lower() for part in _NAT_RE.split(name)]


def even(value) -> int:
    """取最近的偶数（H.264 4:2:0 的裁剪量必须是偶数）。"""
    return int(round(float(value) / 2.0)) * 2


def format_duration(seconds: float) -> str:
    """把秒数变成「1 小时 23 分 / 45 秒」这种给人看的文字。"""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f'{hours} 小时 {minutes} 分'
    if minutes:
        return f'{minutes} 分 {secs} 秒'
    return f'{secs} 秒'


# ---------------------------------------------------------------- 可执行文件

def _project_root(project_root: str = None) -> str:
    if project_root:
        return os.path.abspath(project_root)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_binary(names: tuple, project_root: str = None) -> str:
    """在项目内的 ffmpeg 目录和 PATH 里找可执行文件，找不到返回空串。"""
    root = _project_root(project_root)
    key = (names, root)
    if key in _BIN_CACHE:
        return _BIN_CACHE[key]

    stems = {os.path.splitext(name.lower())[0] for name in names}
    candidates = []
    for base in (os.path.join(root, 'ffmpeg'), root):
        if os.path.isdir(base):
            for walk_root, _dirs, files in os.walk(base):
                for name in files:
                    if os.path.splitext(name.lower())[0] in stems:
                        candidates.append(os.path.join(walk_root, name))
    for name in names:
        which = shutil.which(name)
        if which:
            candidates.append(which)
    # 有些用户只把 ffmpeg.exe 放进项目 ffmpeg 目录，ffprobe 需从同目录找
    ffmpeg = _BIN_CACHE.get((('ffmpeg', 'ffmpeg.exe'), root))
    if ffmpeg:
        for name in names:
            candidates.append(os.path.join(os.path.dirname(ffmpeg), name))

    for cand in candidates:
        try:
            result = subprocess.run([cand, '-version'], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                _BIN_CACHE[key] = cand
                return cand
        except Exception:
            continue
    _BIN_CACHE[key] = ''
    return ''


def find_ffmpeg(project_root: str = None) -> str:
    path = _find_binary(('ffmpeg', 'ffmpeg.exe'), project_root)
    if not path:
        raise MediaError('未找到 ffmpeg，请先安装（winget install Gyan.FFmpeg）或放到项目 ffmpeg 目录')
    return path


def find_ffprobe(project_root: str = None) -> str:
    path = _find_binary(('ffprobe', 'ffprobe.exe'), project_root)
    if not path:
        raise MediaError('未找到 ffprobe，通常与 ffmpeg 一起安装（Gyan 等完整构建都会带）')
    return path


def _startupinfo():
    """Windows 下避免弹出控制台窗口。"""
    if os.name != 'nt':
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def _run(cmd: list, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout, startupinfo=_startupinfo(),
    )


# ---------------------------------------------------------------- 媒体探测

def _ratio_to_float(value) -> float:
    """'45/1' / '30000/1001' -> float。"""
    if not value:
        return 0.0
    try:
        if '/' in str(value):
            num, den = str(value).split('/', 1)
            den = float(den)
            return float(num) / den if den else 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def probe(path: str, project_root: str = None) -> dict:
    """返回精简的媒体信息；非视频文件或无法解析时抛 MediaError。"""
    if not os.path.isfile(path):
        raise MediaError(f'文件不存在: {path}')
    cache_key = _cache_key(path, 'probe')
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    ffprobe = find_ffprobe(project_root)
    result = _run([
        ffprobe, '-v', 'error', '-print_format', 'json',
        '-show_format', '-show_streams', path,
    ], timeout=120)
    if result.returncode != 0:
        raise MediaError(f'无法解析媒体文件: {os.path.basename(path)}')
    try:
        data = json.loads(result.stdout or '{}')
    except json.JSONDecodeError:
        raise MediaError(f'ffprobe 返回内容无法解析: {os.path.basename(path)}') from None

    streams = data.get('streams') or []
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if video is None:
        raise MediaError(f'不是视频文件: {os.path.basename(path)}')

    fmt = data.get('format') or {}
    duration = _ratio_to_float(fmt.get('duration'))
    if not duration:
        duration = max((_ratio_to_float(s.get('duration')) for s in streams), default=0.0)

    stat = os.stat(path)
    video_info = {
        'codec': video.get('codec_name') or '',
        'profile': video.get('profile') or '',
        'width': int(video.get('width') or 0),
        'height': int(video.get('height') or 0),
        'pix_fmt': video.get('pix_fmt') or '',
        'fps': round(_ratio_to_float(video.get('r_frame_rate')), 6),
        'avg_fps': round(_ratio_to_float(video.get('avg_frame_rate')), 6),
        'sar': video.get('sample_aspect_ratio') or '1:1',
        'dar': video.get('display_aspect_ratio') or '',
        'nb_frames': int(video.get('nb_frames') or 0),
        'bit_rate': int(video.get('bit_rate') or 0),
    }
    audio_info = None
    if audio is not None:
        audio_info = {
            'codec': audio.get('codec_name') or '',
            'sample_rate': int(audio.get('sample_rate') or 0),
            'channels': int(audio.get('channels') or 0),
            'bit_rate': int(audio.get('bit_rate') or 0),
        }
    return _cache_put(cache_key, {
        'path': os.path.abspath(path),
        'name': os.path.basename(path),
        'size': stat.st_size,
        'mtime': stat.st_mtime,
        'duration': round(duration, 3),
        'video': video_info,
        'audio': audio_info,
    })

# ---------------------------------------------------------------- 黑边检测

def detect_content_box(path: str, duration: float = 0.0, samples: int = 5,
                       limit: int = 24, project_root: str = None) -> dict:
    """用 cropdetect 找出「画面真实内容」的边界框。

    在不同时间点采样多次，取面积最大的那个框——这样即使某些帧画面偏暗，
    也不会把内容误判成黑边而裁掉。
    """
    ffmpeg = find_ffmpeg(project_root)
    if not duration or duration <= 0:
        duration = SAMPLE_SECONDS * samples
    samples = max(1, min(int(samples), 12))

    cache_key = _cache_key(path, f'box:{samples}:{limit}')
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    boxes = []
    for index in range(samples):
        moment = duration * (index + 0.5) / samples
        result = _run([
            ffmpeg, '-hide_banner', '-nostdin',
            '-ss', f'{moment:.3f}', '-i', path, '-t', f'{SAMPLE_SECONDS:.2f}',
            '-vf', f'cropdetect=limit={limit}:round=2:reset=1',
            '-f', 'null', '-',
        ], timeout=300)
        matches = _CROP_RE.findall(result.stderr or '')
        if not matches:
            continue
        width, height, x, y = (int(v) for v in matches[-1])
        if width <= 0 or height <= 0:
            continue
        boxes.append({'width': width, 'height': height, 'x': x, 'y': y})

    if not boxes:
        return {'ok': False, 'reason': '无法检测画面边界（可能是纯黑或解码失败）', 'samples': []}

    best = max(boxes, key=lambda b: b['width'] * b['height'])
    return _cache_put(cache_key, {
        'ok': True,
        'width': best['width'],
        'height': best['height'],
        'x': best['x'],
        'y': best['y'],
        'samples': boxes,
        'reason': '',
    })


# ---------------------------------------------------------------- 16:9 方案

def _align16(value: int) -> int:
    return ((int(value) + 15) // 16) * 16


def frame_16x9_crop(width: int, height: int) -> dict:
    """把整帧裁成 16:9：优先裁上下，其次裁左右。

    仅在「没有黑边可裁、但用户明确允许切画面」时才用，属于兜底方案。
    """
    target_h = even(width * 9 / 16)
    if 0 < target_h <= height:
        return {'width': int(width), 'height': target_h, 'x': 0, 'y': 0}
    target_w = even(height * 16 / 9)
    if 0 < target_w <= width:
        return {'width': target_w, 'height': int(height), 'x': (int(width) - target_w) // 2, 'y': 0}
    return {'width': even(width), 'height': even(height), 'x': 0, 'y': 0}


def plan_to16x9(info: dict, box: dict, tolerance: int = 8) -> dict:
    """根据探测结果和内容边界框，给出「转 16:9」的具体做法。

    返回的 action 取值：
        none    —— 已经是 16:9 且没有明显黑边，无需处理；
        crop    —— 裁掉黑边即可；mode 说明走无损(sps)还是必须重编码(reencode)；
        blocked —— 裁切会切掉大量真实画面，需要用户显式允许。
    """
    video = info['video']
    frame_w, frame_h = video['width'], video['height']
    warnings = []

    content_x, content_y = box['x'], box['y']
    content_w, content_h = box['width'], box['height']
    # cropdetect 会把画面最外侧 1~2 像素也算成黑，放宽后再判断「贴边」
    full_width = content_x <= 4 and content_x + content_w >= frame_w - 4
    full_height = content_y <= 4 and content_y + content_h >= frame_h - 4
    content_bottom = min(frame_h, content_y + content_h + 2)

    target_h = even(frame_w * 9 / 16)
    target_w = even(frame_h * 16 / 9)

    if target_h <= 0 or target_w <= 0:
        return {'action': 'blocked', 'reason': '无法计算 16:9 目标尺寸', 'warnings': warnings}

    # 情况 1：上下有黑边、左右贴边 —— 最常见（录制时把 16:9 画面塞进更高的画布）
    if full_width and not full_height:
        if target_h > frame_h:
            return {'action': 'blocked', 'reason': '画面比 16:9 更宽，无法通过裁剪得到 16:9',
                    'warnings': warnings}
        if content_y <= 4:
            crop_y = 0                      # 裁掉底部黑边，保持顶部不动
            anchor = 'bottom'
        elif content_bottom >= frame_h:
            crop_y = frame_h - target_h     # 裁掉顶部黑边，保持底部不动
            anchor = 'top'
        else:
            crop_y = max(0, min(content_y, frame_h - target_h))
            anchor = 'middle'

        # cropdetect 常把画面最外 1~2 像素的暗边也算进黑边，
        # 所以「会不会切到内容」按实测值判断，另留一个 2 行的安全余量给 keep_black。
        measured_bottom = content_y + content_h
        lost = 0
        if anchor == 'bottom':
            lost = max(0, measured_bottom - target_h)
        elif anchor == 'top':
            lost = max(0, (frame_h - target_h) - content_y)
        else:
            lost = max(0, measured_bottom - (crop_y + target_h))
        keep_black = max(0, target_h - content_bottom) if anchor == 'bottom' else 0

        if lost > tolerance:
            warnings.append(f'按 16:9 裁切会切掉画面 {lost} 行内容')
            return {'action': 'blocked', 'reason': f'会切掉 {lost} 行画面内容', 'warnings': warnings}
        if lost > 0:
            warnings.append(f'裁切会切掉画面边缘 {lost} 行（阈值内，通常可忽略）')
        if keep_black > tolerance:
            warnings.append(f'画面本身比 16:9 更宽，裁完底部仍会保留 {keep_black} 行黑边')

        plan = {
            'action': 'crop',
            'anchor': anchor,
            'target_width': frame_w,
            'target_height': target_h,
            'crop': {'width': frame_w, 'height': target_h, 'x': 0, 'y': crop_y},
            'removed_rows': frame_h - target_h,
            'lost_rows': lost,
            'keep_black_rows': keep_black,
            'warnings': warnings,
            'reason': '',
        }
        plan['mode'] = 'sps' if (video['codec'] == 'h264' and crop_y == 0) else 'reencode'
        if plan['mode'] == 'reencode' and video['codec'] == 'h264':
            warnings.append('从顶部裁切无法用 SPS 元数据无损完成，改为重编码')
        return plan

    # 情况 2：左右有黑边、上下贴边（竖屏/方屏塞进 16:9 画布）
    if full_height and not full_width:
        if target_w > frame_w:
            return {'action': 'blocked', 'reason': '画面比 16:9 更高，无法通过裁剪得到 16:9',
                    'warnings': warnings}
        # 把 16:9 的窗口居中放到内容上，再夹到画布范围内
        crop_x = content_x + (content_w - target_w) // 2
        crop_x = even(max(0, min(crop_x, frame_w - target_w)))
        lost = max(0, content_w - target_w)
        if lost > tolerance:
            warnings.append(f'按 16:9 裁切会切掉画面 {lost} 列内容')
            return {'action': 'blocked', 'reason': f'会切掉 {lost} 列画面内容', 'warnings': warnings}
        plan = {
            'action': 'crop',
            'anchor': 'left-right',
            'target_width': target_w,
            'target_height': frame_h,
            'crop': {'width': target_w, 'height': frame_h, 'x': crop_x, 'y': 0},
            'removed_cols': frame_w - target_w,
            'lost_cols': lost,
            'warnings': warnings,
            'reason': '',
            'mode': 'reencode',   # SPS 只能解决上下裁剪，左右必须重编码
        }
        return plan

    # 情况 3：画面本身没有黑边
    ratio = frame_w / frame_h if frame_h else 0
    if abs(ratio - 16 / 9) <= 0.01:
        return {'action': 'none', 'reason': '已经是 16:9，无需处理', 'warnings': warnings,
                'target_width': frame_w, 'target_height': frame_h}

    warnings.append(f'画面比例是 {ratio:.3f}:1，没有可裁的黑边；强制转 16:9 会改变画面内容')
    return {'action': 'blocked', 'reason': '画面已铺满且不是 16:9，无法通过裁黑边转换',
            'warnings': warnings}


def analyze_file(path: str, samples: int = 5, project_root: str = None) -> dict:
    """探测单个文件并给出 16:9 处理建议。"""
    info = probe(path, project_root)
    box = detect_content_box(path, info['duration'], samples=samples, project_root=project_root)
    plan = plan_to16x9(info, box) if box.get('ok') else {
        'action': 'blocked', 'reason': box.get('reason', '无法检测黑边'), 'warnings': [],
    }
    recent = (time.time() - info['mtime']) < RECENT_WRITE_SECONDS
    warnings = list(plan.get('warnings') or [])
    if recent:
        warnings.append('该文件最近仍在写入（可能正在录制），处理结果可能不完整')
    return {
        'path': info['path'],
        'name': info['name'],
        'ok': True,
        'error': '',
        'size': info['size'],
        'duration': info['duration'],
        'video': info['video'],
        'audio': info['audio'],
        'box': box,
        'plan': plan,
        'warnings': warnings,
        'recently_written': recent,
    }


def analyze_selection(paths: list, samples: int = 5, project_root: str = None) -> dict:
    """分析一组文件：逐项给出 16:9 建议，并对整组做合并可行性检查。"""
    if not paths:
        raise MediaError('没有选择文件')
    items = []
    infos = []
    for path in paths:
        try:
            info = probe(path, project_root)
            infos.append(info)
            items.append(analyze_file(path, samples=samples, project_root=project_root))
        except MediaError as exc:
            items.append({'path': os.path.abspath(path), 'name': os.path.basename(path),
                          'ok': False, 'error': str(exc)})

    merge = {'ok': False, 'problems': [], 'warnings': [], 'count': len(paths),
             'total_duration': round(sum(i['duration'] for i in infos), 3),
             'total_size': sum(i['size'] for i in infos)}
    if len(infos) >= 2 and len(infos) == len(paths):
        compat = check_compat(infos)
        merge.update(compat)
        merge['ok'] = compat['ok']
        merge['output_suggestion'] = derive_output_path(paths, '合并')
    elif len(infos) == 1:
        merge['problems'].append('至少需要选择 2 个文件才能合并')
    else:
        merge['problems'].append('部分文件无法解析，无法合并')
    return {'items': items, 'merge': merge}


# ---------------------------------------------------------------- 合并可行性

def check_compat(infos: list) -> dict:
    """检查多段能否直接 stream copy 拼接（编码参数必须一致）。"""
    problems, warnings = [], []
    if len(infos) < 2:
        return {'ok': False, 'problems': ['至少需要 2 个文件'], 'warnings': warnings}

    first = infos[0]
    ref = first['video']
    for info in infos[1:]:
        cur = info['video']
        label = info['name']
        if cur['codec'] != ref['codec']:
            problems.append(f'{label}: 视频编码 {cur["codec"]} 与首段 {ref["codec"]} 不同')
        if (cur['width'], cur['height']) != (ref['width'], ref['height']):
            problems.append(
                f'{label}: 分辨率 {cur["width"]}x{cur["height"]} 与首段 {ref["width"]}x{ref["height"]} 不同')
        if cur['pix_fmt'] != ref['pix_fmt']:
            problems.append(f'{label}: 像素格式 {cur["pix_fmt"]} 与首段 {ref["pix_fmt"]} 不同')
        if abs(cur['fps'] - ref['fps']) > 0.05:
            problems.append(f'{label}: 帧率 {cur["fps"]:.3f} 与首段 {ref["fps"]:.3f} 不同')
        if cur['sar'] != ref['sar']:
            problems.append(f'{label}: 像素宽高比 {cur["sar"]} 与首段 {ref["sar"]} 不同')

        a_ref, a_cur = first['audio'], info['audio']
        if (a_ref is None) != (a_cur is None):
            warnings.append(f'{label}: 音轨有无与首段不一致，合并后可能有一段无声')
        elif a_ref and a_cur:
            if (a_cur['codec'], a_cur['sample_rate'], a_cur['channels']) != \
                    (a_ref['codec'], a_ref['sample_rate'], a_ref['channels']):
                problems.append(
                    f'{label}: 音频 {a_cur["codec"]}/{a_cur["sample_rate"]}Hz/{a_cur["channels"]}ch '
                    f'与首段 {a_ref["codec"]}/{a_ref["sample_rate"]}Hz/{a_ref["channels"]}ch 不同')
    if not problems:
        warnings.append('各段编码参数一致，将用 stream copy 无损拼接（不重新编码）')
    return {'ok': not problems, 'problems': problems, 'warnings': warnings}


# ---------------------------------------------------------------- 输出路径

def derive_output_path(paths: list, suffix: str, out_dir: str = None, ext: str = '.mp4') -> str:
    """按首段文件名派生输出名，去掉 _000 这类分段序号，并避免覆盖已有文件。"""
    first = os.path.abspath(paths[0] if isinstance(paths, (list, tuple)) else paths)
    directory = out_dir or os.path.dirname(first)
    stem = os.path.splitext(os.path.basename(first))[0]
    stem = re.sub(r'_\d{2,4}$', '', stem) or stem
    base = f'{stem}_{suffix}'
    candidate = os.path.join(directory, base + ext)
    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f'{base} ({counter})' + ext)
        counter += 1
    return candidate


# ---------------------------------------------------------------- 进度执行

def _job_update(job, percent: float = None, message: str = None):
    if job is not None:
        job.update(percent=percent, message=message)


def _job_check(job):
    if job is not None:
        job.raise_if_cancelled()


def _job_output(job, path: str):
    """告诉任务对象产出路径，取消时它会把半成品删掉。"""
    setter = getattr(job, 'set_output', None)
    if setter is not None:
        setter(path)


def _low_priority_kwargs() -> dict:
    """让重编码进程以低优先级运行。

    录制结束后的自动处理会和下一次开播抢 CPU，把编码器降级能明显减少对录制的干扰
    （录制时丢帧是不可逆的损失，编码慢一点无所谓）。
    """
    if os.name == 'nt':
        flags = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0x00004000)
        return {'creationflags': flags}
    try:
        return {'preexec_fn': lambda: os.nice(19)}
    except (AttributeError, OSError):
        return {}


def _run_with_progress(cmd: list, total_duration: float, job=None, timeout: int = 86400,
                       low_priority: bool = False) -> str:
    """执行 ffmpeg 并解析 `-progress pipe:1` 输出，返回 stderr/stdout 尾部文本。"""
    _job_check(job)
    extra = _low_priority_kwargs() if low_priority else {}
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace',
        bufsize=1, startupinfo=_startupinfo(), **extra,
    )
    if job is not None:
        job.attach_process(process)

    tail = []
    started = time.time()
    speed = 0.0
    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            if line.startswith('out_time_us='):
                try:
                    elapsed = int(line.split('=', 1)[1]) / 1_000_000.0
                except ValueError:
                    continue
                if total_duration > 0:
                    percent = min(99.0, max(0.0, elapsed / total_duration * 100.0))
                    # 长任务（AV1 可能要好几小时）必须让用户看到还要等多久
                    if speed > 0 and total_duration > elapsed:
                        remain = (total_duration - elapsed) / speed
                        _job_update(job, percent,
                                    f'已处理 {percent:.0f}%，剩余约 {format_duration(remain)}')
                    else:
                        _job_update(job, percent)
            elif line.startswith('speed='):
                raw = line.split('=', 1)[1].strip().rstrip('x')
                try:
                    speed = float(raw)
                except ValueError:
                    speed = 0.0
            elif '=' not in line:
                tail.append(line)
                del tail[:-40]
            if time.time() - started > timeout:
                process.kill()
                raise MediaError('处理超时')
            _job_check(job)
        process.wait(timeout=30)
    finally:
        if job is not None:
            job.attach_process(None)
        if process.poll() is None:
            process.kill()

    output = '\n'.join(tail).strip()
    if process.returncode != 0:
        _job_check(job)
        detail = output.splitlines()[-3:] if output else ['ffmpeg 返回非零退出码']
        raise MediaError('ffmpeg 执行失败: ' + ' | '.join(detail))
    return output


# ---------------------------------------------------------------- 合并

def prepare_merge(paths: list, project_root: str = None, out_dir: str = None,
                  order: str = 'name') -> dict:
    """同步校验合并请求（快），返回可直接交给后台任务执行的数据。"""
    if not paths or len(paths) < 2:
        raise MediaError('请选择至少 2 个文件再合并')
    resolved = [os.path.abspath(p) for p in paths]
    for path in resolved:
        if not os.path.isfile(path):
            raise MediaError(f'文件不存在: {path}')
    if order == 'name':
        resolved.sort(key=lambda p: natural_key(os.path.basename(p)))

    infos = [probe(p, project_root) for p in resolved]
    compat = check_compat(infos)
    if not compat['ok']:
        raise MediaError('这些文件编码参数不一致，无法无损合并：' + '；'.join(compat['problems'][:4]))

    output = derive_output_path(resolved, '合并', out_dir=out_dir)
    recent = [i['name'] for i in infos if (time.time() - i['mtime']) < RECENT_WRITE_SECONDS]
    return {
        'paths': resolved,
        'infos': infos,
        'output': output,
        'total_duration': sum(i['duration'] for i in infos),
        'total_size': sum(i['size'] for i in infos),
        'warnings': compat['warnings'] + (
            [f'以下文件最近仍在写入，可能正在录制：{", ".join(recent[:3])}'] if recent else []),
    }


def merge(paths: list, project_root: str = None, out_dir: str = None, job=None,
          faststart: bool = True, drop_source: bool = False, order: str = 'name',
          output: str = None) -> dict:
    """把多段视频无损拼接为单个 mp4。"""
    prepared = prepare_merge(paths, project_root, out_dir, order)
    output = os.path.abspath(output) if output else prepared['output']
    total = prepared['total_duration']
    _job_output(job, output)
    _job_update(job, 0.0, f'准备合并 {len(prepared["paths"])} 个文件')

    if os.path.exists(output):
        raise MediaError(f'输出文件已存在: {output}')

    ffmpeg = find_ffmpeg(project_root)
    list_path = None
    try:
        import tempfile
        handle, list_path = tempfile.mkstemp(prefix='dlr_concat_', suffix='.txt')
        os.close(handle)
        with open(list_path, 'w', encoding='utf-8', newline='\n') as fp:
            for path in prepared['paths']:
                # concat demuxer 用单引号包裹，路径里的单引号需转义
                safe = path.replace('\\', '/').replace("'", "'\\''")
                fp.write(f"file '{safe}'\n")

        cmd = [
            ffmpeg, '-hide_banner', '-y', '-nostdin',
            '-f', 'concat', '-safe', '0', '-i', list_path,
            '-map', '0', '-c', 'copy', '-map_metadata', '0',
        ]
        if faststart:
            cmd += ['-movflags', '+faststart']
        cmd += ['-progress', 'pipe:1', '-nostats', output]

        _job_update(job, 1.0, '正在无损拼接（stream copy）')
        _run_with_progress(cmd, total, job)
    finally:
        if list_path and os.path.exists(list_path):
            try:
                os.remove(list_path)
            except OSError:
                pass

    if not os.path.exists(output):
        raise MediaError('合并失败：未生成输出文件')
    _job_update(job, 100.0, '合并完成')

    result = {
        'output': output,
        'name': os.path.basename(output),
        'size': os.path.getsize(output),
        'count': len(prepared['paths']),
        'total_duration': total,
        'warnings': prepared['warnings'],
        'lossless': True,
    }
    if drop_source:
        removed, errors = [], []
        for path in prepared['paths']:
            try:
                os.remove(path)
                removed.append(path)
            except OSError as exc:
                errors.append(f'{os.path.basename(path)}: {exc}')
        result['removed'] = removed
        result['remove_errors'] = errors
    return result


# ---------------------------------------------------------------- 16:9 裁切

def _calibrate_sps(path: str, target_h: int, frame_h: int, crop_y: int,
                   project_root: str = None) -> dict:
    """先用 2 秒样本验证 SPS 裁剪参数确实能得到目标高度，再上全片。

    这样做是因为 SPS 的裁剪量单位/编码高度不能百分百从容器信息推断，
    与其猜，不如花两秒实测一把——失败就退回重编码，不会产出坏文件。
    """
    coded_h = _align16(frame_h)
    crop_bottom = coded_h - crop_y - target_h
    if crop_bottom <= 0 or crop_bottom % 2 != 0 or crop_y % 2 != 0:
        return {'ok': False, 'reason': '裁剪量不是合法偶数，无法走无损路径'}
    if crop_bottom > 16000 or crop_y > 16000:
        return {'ok': False, 'reason': '裁剪量超出 H.264 允许范围'}

    ffmpeg = find_ffmpeg(project_root)
    ffprobe = find_ffprobe(project_root)
    import tempfile
    handle, sample = tempfile.mkstemp(prefix='dlr_sps_', suffix='.mp4')
    os.close(handle)
    try:
        expr = f'h264_metadata=crop_bottom={crop_bottom}'
        if crop_y:
            expr += f':crop_top={crop_y}'
        result = _run([
            ffmpeg, '-hide_banner', '-y', '-nostdin', '-ss', '0', '-t', '2',
            '-i', path, '-map', '0', '-c', 'copy', '-bsf:v', expr, sample,
        ], timeout=180)
        if result.returncode != 0:
            return {'ok': False, 'reason': 'ffmpeg 拒绝改写 SPS', 'crop_bottom': crop_bottom}
        check = _run([
            ffprobe, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'json', sample,
        ], timeout=60)
        try:
            streams = json.loads(check.stdout or '{}').get('streams') or []
        except json.JSONDecodeError:
            streams = []
        if not streams:
            return {'ok': False, 'reason': '样本探测失败', 'crop_bottom': crop_bottom}
        got_h = int(streams[0].get('height') or 0)
        if got_h != target_h:
            return {'ok': False, 'crop_bottom': crop_bottom,
                    'reason': f'实测裁剪后高度为 {got_h}，与目标 {target_h} 不符'}
        return {'ok': True, 'crop_bottom': crop_bottom, 'crop_top': crop_y,
                'reason': '', 'sample_height': got_h}
    finally:
        if os.path.exists(sample):
            try:
                os.remove(sample)
            except OSError:
                pass


def _reencode_aspect(path: str, output: str, crop: dict, info: dict, job=None,
                     crf: int = DEFAULT_CRF, preset: str = DEFAULT_PRESET,
                     project_root: str = None, low_priority: bool = False) -> dict:
    """重编码裁切（兼容非 H.264 / 需要裁左右的情况）。音轨尽量原样复制。"""
    ffmpeg = find_ffmpeg(project_root)
    audio = info.get('audio')
    if audio and audio.get('codec') == 'aac':
        audio_args = ['-c:a', 'copy']
    elif audio:
        audio_args = ['-c:a', 'aac', '-b:a', '192k']
    else:
        audio_args = ['-an']

    cmd = [
        ffmpeg, '-hide_banner', '-y', '-nostdin', '-i', path,
        '-map', '0:v:0', '-map', '0:a:0?',
        '-vf', f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']},format=yuv420p",
        '-c:v', 'libx264', '-preset', preset, '-crf', str(crf),
        '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough',
    ] + audio_args + [
        '-map_metadata', '0', '-movflags', '+faststart',
        '-progress', 'pipe:1', '-nostats', output,
    ]
    _job_update(job, 1.0, f'正在重编码裁切（{preset} / CRF {crf}）')
    _run_with_progress(cmd, info['duration'], job, low_priority=low_priority)
    return {'mode': 'reencode', 'lossless': False}


def to_16x9(path: str, project_root: str = None, out_dir: str = None, job=None,
            prefer_lossless: bool = True, crf: int = DEFAULT_CRF,
            preset: str = DEFAULT_PRESET, drop_source: bool = False,
            allow_content_loss: bool = False, output: str = None,
            low_priority: bool = False) -> dict:
    """把单个视频裁成 16:9：优先走 SPS 元数据（无损），否则重编码。"""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise MediaError(f'文件不存在: {path}')
    info = probe(path, project_root)
    _job_update(job, 2.0, '正在检测黑边')

    box = detect_content_box(path, info['duration'], project_root=project_root)
    if not box.get('ok'):
        raise MediaError(box.get('reason') or '无法检测黑边')
    plan = plan_to16x9(info, box)

    action = plan.get('action')
    if action == 'none':
        raise MediaError('该文件已经是 16:9 且没有明显黑边，无需处理')
    if action == 'blocked' and not allow_content_loss:
        raise MediaError(plan.get('reason') or '无法在不切画面的前提下转为 16:9')

    crop = plan.get('crop') or frame_16x9_crop(info['video']['width'], info['video']['height'])
    output = os.path.abspath(output) if output else derive_output_path([path], '16比9', out_dir=out_dir)
    _job_output(job, output)
    if os.path.exists(output):
        raise MediaError(f'输出文件已存在: {output}')

    mode = plan.get('mode', 'reencode')
    lossless = False
    detail = ''

    if mode == 'sps' and prefer_lossless:
        _job_update(job, 5.0, '正在校验无损裁剪参数')
        calibration = _calibrate_sps(path, plan['target_height'], info['video']['height'],
                                     crop['y'], project_root)
        if calibration.get('ok'):
            ffmpeg = find_ffmpeg(project_root)
            expr = f"h264_metadata=crop_bottom={calibration['crop_bottom']}"
            if calibration.get('crop_top'):
                expr += f":crop_top={calibration['crop_top']}"
            cmd = [
                ffmpeg, '-hide_banner', '-y', '-nostdin', '-i', path,
                '-map', '0', '-c', 'copy', '-bsf:v', expr,
                '-map_metadata', '0', '-movflags', '+faststart',
                '-progress', 'pipe:1', '-nostats', output,
            ]
            _job_update(job, 8.0, '正在改写裁剪元数据（不重新编码）')
            _run_with_progress(cmd, info['duration'], job, low_priority=low_priority)
            lossless = True
            detail = f"crop_bottom={calibration['crop_bottom']}"
        else:
            _job_update(job, 5.0, f"无损路径不可用（{calibration.get('reason')}），改为重编码")
            mode = 'reencode'

    if mode != 'sps' or not lossless:
        _reencode_aspect(path, output, crop, info, job, crf, preset, project_root,
                         low_priority=low_priority)
        lossless = False

    if not os.path.exists(output):
        raise MediaError('处理失败：未生成输出文件')
    _job_update(job, 100.0, '完成')

    result = {
        'output': output,
        'name': os.path.basename(output),
        'size': os.path.getsize(output),
        'mode': 'sps' if lossless else 'reencode',
        'lossless': lossless,
        'detail': detail,
        'source': path,
        'source_size': info['size'],
        'crop': crop,
        'removed_rows': info['video']['height'] - crop['height'],
        'removed_cols': info['video']['width'] - crop['width'],
        'warnings': plan.get('warnings') or [],
    }
    if drop_source and lossless:
        try:
            os.remove(path)
            result['removed_source'] = True
        except OSError as exc:
            result['remove_errors'] = [str(exc)]
    return result


# ---------------------------------------------------------------- 压缩转码

# 压缩强度 -> 目标码率 = 源视频码率 × ratio
#
# 为什么用「目标码率」而不是 CRF：CRF 是「按画质」编码，它保证画质但不保证体积变小。
# 实测：一个已经压到 5.1 Mbps 的录像，用 CRF21 重编码出来还是 5.10 Mbps（体积 100%），
# 用户会以为功能坏了。改成按源码率打折，体积才变得可预期。
# 实测（1080p60 真实素材，源 5.10 Mbps，SSIM 以原片为参考）：
#   50% -> 2.44 Mbps, SSIM .9716 ; 35% -> 1.68 Mbps, .9589 ; 25% -> 1.18 Mbps, .9402
COMPRESS_LEVELS = {
    'light': {'ratio': 0.70, 'label': '轻度', 'note': '体积降到约 70%，肉眼很难看出差别'},
    'medium': {'ratio': 0.50, 'label': '中等', 'note': '体积减半，日常观看够用'},
    'strong': {'ratio': 0.30, 'label': '强力', 'note': '体积降到约三成，快速画面会开始糊'},
}

# 编码器 -> 参数。AV1 统一 preset 6：SVT 官方警告 preset>=10 是给自动化工具用的、
# 可能出现画质问题（实测同码率下 preset10 的 SSIM 反而低于 H.264）。
CODEC_SETTINGS = {
    'h264': {'codec': 'libx264', 'preset': 'veryfast', 'speed_fps': 150.0,
             'label': 'H.264（快，兼容所有播放器）'},
    'av1': {'codec': 'libsvtav1', 'preset': 6, 'speed_fps': 41.0,
            'label': 'AV1（同码率画质更好，但很慢，老设备可能不支持）'},
}


def presets_info() -> dict:
    """给前端用的编码器 / 压缩强度与耗时预估。速度按 1080p60 实测折算。"""
    frames_per_source_hour = 3600 * 60
    codecs = []
    for codec, meta in CODEC_SETTINGS.items():
        speed = meta.get('speed_fps') or 0
        codecs.append({
            'id': codec,
            'label': meta['label'],
            'speed_fps': speed,
            'minutes_per_source_hour': round(frames_per_source_hour / speed / 60, 1) if speed else None,
        })
    levels = [dict(id=level_id, **meta) for level_id, meta in COMPRESS_LEVELS.items()]
    return {'codecs': codecs, 'levels': levels}


def _video_bitrate(info: dict) -> int:
    """源视频码率（bps）；容器没给就按总大小减去音频估算。"""
    bitrate = int((info['video'] or {}).get('bit_rate') or 0)
    if bitrate > 0:
        return bitrate
    audio_bitrate = int((info.get('audio') or {}).get('bit_rate') or 0)
    duration = info.get('duration') or 0
    if duration > 0:
        return max(1, int(info['size'] * 8 / duration - audio_bitrate))
    return 0


def estimate_compress(info: dict, level: str = 'medium') -> dict:
    """估算按某个强度压缩后的体积，让用户点「开始」之前就知道会变成多大。"""
    if level not in COMPRESS_LEVELS:
        raise MediaError(f'不支持的压缩强度: {level}')
    ratio = COMPRESS_LEVELS[level]['ratio']
    video_bitrate = _video_bitrate(info)
    if video_bitrate <= 0:
        return {'ok': False, 'reason': '无法获取源视频码率，无法估算体积'}
    audio_bitrate = int((info.get('audio') or {}).get('bit_rate') or 0)
    target_video = max(1, int(video_bitrate * ratio))
    target_total = target_video + audio_bitrate
    duration = info.get('duration') or 0
    estimated_size = int(target_total * duration / 8) if duration else 0
    return {
        'ok': True,
        'level': level,
        'ratio': ratio,
        'source_video_bitrate': video_bitrate,
        'target_video_bitrate': target_video,
        'audio_bitrate': audio_bitrate,
        'estimated_size': estimated_size,
        'source_size': info['size'],
        'estimated_ratio': round(estimated_size / info['size'], 4) if info['size'] else None,
    }


def compress(path: str, project_root: str = None, out_dir: str = None, job=None,
             codec: str = 'h264', level: str = 'medium', crop_to_16x9: bool = True,
             drop_source: bool = False, output: str = None,
             allow_content_loss: bool = False, low_priority: bool = False) -> dict:
    """把视频重编码成更小的 MP4，可选在同一趟里裁掉黑边转 16:9。

    压缩强度按「源码率 × ratio」决定目标码率，因此体积是可预期的；
    代价是画面会再经历一次有损压缩。H.264 很快，AV1 很慢。
    """
    codec = (codec or 'h264').lower()
    level = (level or 'medium').lower()
    if codec not in CODEC_SETTINGS:
        raise MediaError(f'不支持的编码器: {codec}')
    if level not in COMPRESS_LEVELS:
        raise MediaError(f'不支持的压缩强度: {level}')

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise MediaError(f'文件不存在: {path}')
    info = probe(path, project_root)
    settings = CODEC_SETTINGS[codec]
    estimate = estimate_compress(info, level)
    if not estimate.get('ok'):
        raise MediaError(estimate.get('reason') or '无法估算目标码率')
    target_video = estimate['target_video_bitrate']

    # 顺便处理黑边：既然要重编码，裁掉黑边是免费的
    crop = None
    warnings = []
    if crop_to_16x9:
        _job_update(job, 1.0, '正在检测黑边')
        box = detect_content_box(path, info['duration'], project_root=project_root)
        if box.get('ok'):
            plan = plan_to16x9(info, box)
            action = plan.get('action')
            if action == 'crop':
                crop = plan['crop']
                warnings.extend(plan.get('warnings') or [])
            elif action == 'blocked' and allow_content_loss:
                crop = frame_16x9_crop(info['video']['width'], info['video']['height'])
                warnings.append('按 16:9 裁切会切掉部分画面（你已允许）')
            elif action == 'blocked':
                warnings.append(f'未裁边：{plan.get("reason")}')
        else:
            warnings.append(f'未裁边：{box.get("reason")}')

    suffix = 'AV1' if codec == 'av1' else '压缩'
    output = os.path.abspath(output) if output else derive_output_path([path], suffix, out_dir=out_dir)
    _job_output(job, output)
    if os.path.exists(output):
        raise MediaError(f'输出文件已存在: {output}')

    filters = []
    if crop:
        filters.append(f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']}")
    filters.append('format=yuv420p')

    audio = info.get('audio')
    if audio and audio.get('codec') == 'aac':
        audio_args = ['-c:a', 'copy']
    elif audio:
        audio_args = ['-c:a', 'aac', '-b:a', '192k']
    else:
        audio_args = ['-an']

    ffmpeg = find_ffmpeg(project_root)
    video_args = [
        '-c:v', settings['codec'],
        '-preset', str(settings['preset']),
        '-b:v', str(target_video),
    ]
    if codec == 'h264':
        # 限制峰值码率，避免复杂画面把平均码率顶上去导致体积超出预期
        video_args += ['-maxrate', str(int(target_video * 1.5)),
                       '-bufsize', str(int(target_video * 2))]

    cmd = [
        ffmpeg, '-hide_banner', '-y', '-nostdin', '-i', path,
        '-map', '0:v:0', '-map', '0:a:0?',
        '-vf', ','.join(filters),
    ] + video_args + [
        '-pix_fmt', 'yuv420p',
        '-fps_mode', 'passthrough',
    ] + audio_args + [
        '-map_metadata', '0',
        '-movflags', '+faststart',
        '-progress', 'pipe:1', '-nostats',
        output,
    ]

    label = 'AV1' if codec == 'av1' else 'H.264'
    _job_update(job, 2.0,
                f'开始用 {label} 重编码（目标 {target_video / 1e6:.2f} Mbps，'
                f'{COMPRESS_LEVELS[level]["label"]}）')
    _run_with_progress(cmd, info['duration'], job, low_priority=low_priority)

    if not os.path.exists(output):
        raise MediaError('压缩失败：未生成输出文件')

    size = os.path.getsize(output)
    source_size = info['size']
    saved_ratio = round(1 - size / source_size, 4) if source_size else 0
    if saved_ratio < 0.05:
        warnings.append('压缩后体积几乎没变：这个文件的码率本来就很低，'
                        '换更强的压缩强度或改用 AV1 才有明显效果')
    return {
        'output': output,
        'name': os.path.basename(output),
        'size': size,
        'source': path,
        'source_size': source_size,
        'codec': codec,
        'codec_label': label,
        'level': level,
        'level_label': COMPRESS_LEVELS[level]['label'],
        'target_video_bitrate': target_video,
        'estimated_size': estimate.get('estimated_size'),
        'lossless': False,
        'saved_bytes': source_size - size,
        'saved_ratio': saved_ratio,
        'crop': crop,
        'duration': info['duration'],
        'warnings': warnings,
    }


def is_av1_supported(project_root: str = None) -> bool:
    """确认当前 ffmpeg 是否带 AV1 编码器。"""
    try:
        ffmpeg = find_ffmpeg(project_root)
    except MediaError:
        return False
    result = _run([ffmpeg, '-hide_banner', '-encoders'], timeout=30)
    return 'libsvtav1' in (result.stdout or '')


# ---------------------------------------------------------------- 便捷判断

def is_valid_16x9(width: int, height: int, tolerance: float = 0.01) -> bool:
    if not height:
        return False
    return abs(width / height - 16 / 9) <= tolerance
