# -*- coding: utf-8 -*-
"""
可视化控制台接口自检（HTTP 层）

用法：
    1) 先启动服务： python web/server.py --port 8799
    2) 运行本脚本： python web/selftest_api.py --port 8799

脚本会真实调用接口，但会自动把改动还原，不会破坏你的配置。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import requests

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = ''):
    (PASS if condition else FAIL).append(name)
    print(f'  [{"OK " if condition else "FAIL"}] {name}' + (f' -> {detail}' if detail else ''))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8799)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    base = f'http://{args.host}:{args.port}'

    def get(path, **kw):
        return requests.get(base + path, timeout=30, **kw)

    def post(path, payload=None):
        return requests.post(base + path, json=payload or {}, timeout=60)

    print('== 基础接口 ==')
    r = get('/api/ping')
    check('GET /api/ping', r.status_code == 200 and r.json().get('ok'))

    r = get('/api/state')
    state = r.json()
    check('GET /api/state', r.status_code == 200 and 'process' in state)
    check('  版本号解析', bool(state['app']['version']) and state['app']['version'] != 'unknown',
          state['app']['version'])
    check('  已检测 ffmpeg', state['env']['ffmpeg']['ok'], state['env']['ffmpeg'].get('version', ''))
    check('  已检测依赖包', state['env']['dependencies']['ok'],
          'missing=' + str(state['env']['dependencies']['missing']))
    check('  磁盘信息', state['env']['disk']['ok'],
          f"free={state['env']['disk'].get('free_gb')}GB")

    print('== 配置读取 ==')
    r = get('/api/config')
    sections = r.json()['sections']
    names = [s['name'] for s in sections]
    check('GET /api/config 返回 5 个分组', names == ['录制设置', '推送配置', 'Cookie', 'Authorization', '账号密码'],
          str(names))
    flat = {s['name']: {i['key']: i for i in s['items']} for s in sections}
    check('  录制设置含 循环时间', '循环时间(秒)' in flat['录制设置'])
    check('  循环时间类型为 int', flat['录制设置']['循环时间(秒)']['meta']['type'] == 'int')
    check('  是否跳过代理 类型为 bool', flat['录制设置']['是否跳过代理检测(是/否)']['meta']['type'] == 'bool')
    check('  视频格式 为下拉且含 ts', flat['录制设置']['视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频']['meta']['type'] == 'select'
          and 'ts' in flat['录制设置']['视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频']['meta']['options'])
    check('  推送渠道 为多选', flat['推送配置']['直播状态推送渠道']['meta']['type'] == 'multiselect')
    check('  抖音cookie 有必填提示', flat['Cookie']['抖音cookie']['meta'].get('required') is True)

    print('== 配置校验（应当被拒绝）==')
    r = post('/api/config', {'updates': {'录制设置': {'循环时间(秒)': 'abc'}}})
    check('非数字被拒绝', r.status_code == 400, str(r.json().get('error'))[:60])
    r = post('/api/config', {'updates': {'录制设置': {'不存在的键': '1'}}})
    check('未知键被拒绝', r.status_code == 400, str(r.json().get('error'))[:60])
    r = post('/api/config', {'updates': {'不存在的分组': {'a': '1'}}})
    check('未知分组被拒绝', r.status_code == 400, str(r.json().get('error'))[:60])
    r = post('/api/config', {'updates': {'推送配置': {'直播状态推送渠道': '不存在的渠道'}}})
    check('非法推送渠道被拒绝', r.status_code == 400, str(r.json().get('error'))[:60])

    print('== 配置写入与还原 ==')
    original = flat['录制设置']['循环时间(秒)']['value']
    new_value = '111' if original != '111' else '222'
    r = post('/api/config', {'updates': {'录制设置': {'循环时间(秒)': new_value}}})
    check('写入合法值成功', r.status_code == 200 and new_value and r.json().get('changed'),
          str(r.json().get('changed')))
    after = {i['key']: i['value'] for i in get('/api/config').json()['sections'][0]['items']}
    check('  读回一致', after['循环时间(秒)'] == new_value, after['循环时间(秒)'])
    r = post('/api/config', {'updates': {'录制设置': {'循环时间(秒)': original}}})
    check('还原原值', r.status_code == 200 and
          {i['key']: i['value'] for i in get('/api/config').json()['sections'][0]['items']}['循环时间(秒)'] == original)

    print('== 直播间地址管理 ==')
    before = get('/api/urls').json()['total']
    r = post('/api/urls', {'url': 'live.douyin.com/__selftest__', 'quality': '高清', 'name': '自检主播'})
    check('新增地址', r.status_code == 200, str(r.json().get('error', ''))[:80])
    items = get('/api/urls').json()['items']
    check('  地址数量 +1', len(items) == before + 1)
    entry = [i for i in items if '__selftest__' in i['url']]
    check('  能按字段解析', bool(entry) and entry[0]['quality'] == '高清' and entry[0]['name'] == '自检主播',
          str(entry[:1]))
    idx = entry[0]['index'] if entry else -1
    r = post('/api/urls', {'url': 'live.douyin.com/__selftest__'})
    check('重复地址被拒绝', r.status_code == 400, str(r.json().get('error'))[:60])
    r = post('/api/urls/toggle', {'indexes': [idx], 'enabled': False})
    check('停用地址', r.status_code == 200)
    check('  停用后 enabled=False',
          [i for i in get('/api/urls').json()['items'] if i['index'] == idx][0]['enabled'] is False)
    r = post('/api/urls', {'url': 'live.douyin.com/__selftest2__', 'quality': '原画', 'name': '临时'})
    check('批量导入接口', post('/api/urls/import', {'text': 'live.douyin.com/__selftest3__\n坏数据!!\n'}).status_code == 200)
    r = post('/api/urls/delete', {'indexes': [i['index'] for i in get('/api/urls').json()['items']
                                             if '__selftest' in i['url']]})
    check('删除测试地址', r.status_code == 200 and get('/api/urls').json()['total'] == before,
          f"total={get('/api/urls').json()['total']}")

    print('== 日志接口 ==')
    r = get('/api/logs/snapshot')
    check('GET /api/logs/snapshot', r.status_code == 200 and 'items' in r.json())
    r = get('/api/logs/files')
    check('GET /api/logs/files', r.status_code == 200)
    check('  日志目录可枚举（可能为空）', isinstance(r.json()['items'], list))
    if r.json()['items']:
        name = r.json()['items'][0]['name']
        r2 = get('/api/logs/tail', params={'name': name, 'lines': 5})
        check(f'  tail {name}', r2.status_code == 200 and isinstance(r2.json()['lines'], list))
    r = get('/api/logs/tail', params={'name': '../../config/config.ini'})
    check('路径穿越被拦截', r.status_code == 404, str(r.json().get('error'))[:60])

    print('== 文件接口 ==')
    r = get('/api/files')
    check('GET /api/files', r.status_code == 200, str(r.json().get('path')))
    files_data = r.json()
    check('  返回录制目录作为默认根', bool(files_data.get('root')), str(files_data.get('root')))
    check('  录制目录内可删除', files_data.get('deletable') is True)
    check('  返回盘符列表(Windows)', isinstance(files_data.get('drives'), list))
    # 浏览不限制目录，但删除受限
    r = get('/api/files', params={'path': 'C:\\Windows'})
    check('越界目录可浏览', r.status_code == 200, str(r.json().get('error', ''))[:60])
    if r.status_code == 200:
        check('  越界目录标记为不可删除', r.json().get('deletable') is False)
    r = post('/api/files/delete', {'paths': ['C:\\Windows\\notepad.exe']})
    check('越界目录删除被拒绝', r.status_code == 200 and r.json().get('ok') is False
          and not r.json().get('deleted'), str(r.json().get('errors'))[:90])
    r = get('/api/browse')
    check('GET /api/browse', r.status_code == 200 and 'dirs' in r.json(), str(r.json().get('path')))

    print('== 媒体后处理接口 ==')
    r = post('/api/media/analyze', {'paths': []})
    check('analyze 空选择被拒绝(400)', r.status_code == 400, str(r.json().get('error'))[:50])

    r = post('/api/media/analyze', {'paths': [os.path.join(os.sep, 'no_such_file_xyz.mp4')]})
    items = r.json().get('items') or [{}]
    check('analyze 不存在的文件逐项报错', r.status_code == 200 and items[0].get('ok') is False,
          str(items[0].get('error'))[:60])

    r = post('/api/media/merge', {'paths': ['C:\\Windows\\notepad.exe']})
    check('merge 单文件被拒绝(400)', r.status_code == 400, str(r.json().get('error'))[:60])

    r = get('/api/media/jobs')
    check('GET /api/media/jobs', r.status_code == 200 and isinstance(r.json().get('items'), list))

    r = post('/api/media/jobs/cancel', {'id': 'not-a-real-job'})
    check('取消不存在的任务返回 ok=False', r.status_code == 200 and r.json().get('ok') is False)

    r = post('/api/media/to16x9', {'paths': ['C:\\no_such_media_file.mp4']})
    check('to16x9 不存在的文件被拒绝(400)', r.status_code == 400, str(r.json().get('error'))[:60])

    # 端到端：真造一段「底部黑边」视频，走接口转 16:9，确认走无损路径
    tmpdir = ''
    try:
        import media_tools as mt
        ffmpeg = mt.find_ffmpeg()
        tmpdir = tempfile.mkdtemp(prefix='dlr_api_media_')
        clip = os.path.join(tmpdir, 'clip.mp4')
        subprocess.run([
            ffmpeg, '-hide_banner', '-v', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=s=640x360:r=30:d=2',
            '-f', 'lavfi', '-i', 'color=black:s=640x600:r=30:d=2',
            '-filter_complex', '[1:v][0:v]overlay=0:0[v]', '-map', '[v]',
            '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-shortest', clip,
        ], capture_output=True, timeout=120)

        r = post('/api/media/analyze', {'paths': [clip], 'samples': 3})
        plan = ((r.json().get('items') or [{}])[0]).get('plan') or {}
        check('analyze 识别出底部黑边', plan.get('action') == 'crop', str(plan.get('action')))

        r = post('/api/media/to16x9', {'paths': [clip], 'crf': 'abc'})
        check('  crf 非法被拒绝(400)', r.status_code == 400, str(r.json().get('error'))[:50])

        r = post('/api/media/to16x9', {'paths': [clip]})
        jobs = r.json().get('jobs') or [{}]
        job_id = jobs[0].get('id', '')
        check('to16x9 已入队', r.status_code == 200 and bool(job_id))

        job = {}
        for _ in range(80):
            time.sleep(0.5)
            items = get('/api/media/jobs').json().get('items', [])
            job = next((i for i in items if i.get('id') == job_id), {})
            if job.get('status') in ('done', 'error', 'cancelled'):
                break
        check('  任务执行完成', job.get('status') == 'done', str(job.get('error'))[:80])
        result = job.get('result') or {}
        check('  走了无损路径', result.get('lossless') is True, str(result.get('mode')))
        if result.get('output'):
            info = mt.probe(result['output'])
            check('  输出为 640x360',
                  (info['video']['width'], info['video']['height']) == (640, 360),
                  f"{info['video']['width']}x{info['video']['height']}")

        # 压缩：档位元数据 + 参数校验 + 真实跑一次
        r = get('/api/media/presets')
        presets = r.json()
        check('GET /api/media/presets', r.status_code == 200
              and [c['id'] for c in presets.get('codecs', [])] == ['h264', 'av1'])
        check('  返回耗时预估', all(c.get('minutes_per_source_hour')
                                for c in presets.get('codecs', [])))

        r = post('/api/media/compress', {'paths': [clip], 'codec': 'vp9'})
        check('compress 非法编码器被拒绝(400)', r.status_code == 400,
              str(r.json().get('error'))[:50])
        r = post('/api/media/compress', {'paths': [clip], 'codec': 'h264', 'tier': 'ultra'})
        check('compress 非法档位被拒绝(400)', r.status_code == 400,
              str(r.json().get('error'))[:50])

        r = post('/api/media/compress', {'paths': [clip], 'codec': 'h264',
                                         'tier': 'small', 'crop_to_16x9': True})
        jobs = r.json().get('jobs') or [{}]
        cjob_id = jobs[0].get('id', '')
        check('compress 已入队', r.status_code == 200 and bool(cjob_id))
        cjob = {}
        for _ in range(120):
            time.sleep(0.5)
            items = get('/api/media/jobs').json().get('items', [])
            cjob = next((i for i in items if i.get('id') == cjob_id), {})
            if cjob.get('status') in ('done', 'error', 'cancelled'):
                break
        check('  压缩任务完成', cjob.get('status') == 'done', str(cjob.get('error'))[:80])
        cresult = cjob.get('result') or {}
        check('  输出体积小于源', (cresult.get('size') or 0) < (cresult.get('source_size') or 1),
              f"{cresult.get('source_size')} -> {cresult.get('size')}")
        if cresult.get('output'):
            cinfo = mt.probe(cresult['output'])
            check('  输出编码为 h264', cinfo['video']['codec'] == 'h264', cinfo['video']['codec'])
            check('  顺带裁成 640x360',
                  (cinfo['video']['width'], cinfo['video']['height']) == (640, 360),
                  f"{cinfo['video']['width']}x{cinfo['video']['height']}")
    except Exception as exc:  # noqa: BLE001
        check('媒体端到端测试', False, str(exc)[:120])
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print('== 安全防护 ==')
    r = requests.post(base + '/api/control/start', data='{"x":1}',
                      headers={'Content-Type': 'text/plain'}, timeout=20)
    check('拒绝非 JSON 请求体(415)', r.status_code == 415, str(r.json().get('error'))[:50])
    r = requests.post(base + '/api/urls', json={}, headers={'Origin': 'http://evil.example.com'}, timeout=20)
    check('拒绝跨站 Origin(403)', r.status_code == 403, str(r.json().get('error'))[:50])
    r = requests.get(base + '/api/ping', headers={'Host': 'evil.example.com'}, timeout=20)
    check('拒绝伪造 Host(403)', r.status_code == 403, str(r.json().get('error'))[:50])

    print('== SSE 流 ==')
    try:
        with requests.get(base + '/api/logs/stream', stream=True, timeout=12) as resp:
            check('SSE 返回 200', resp.status_code == 200)
            check('SSE Content-Type 正确', 'text/event-stream' in resp.headers.get('Content-Type', ''))
            got = []
            start = time.time()
            for line in resp.iter_lines(decode_unicode=True):
                if line:
                    got.append(line)
                if len(got) >= 3 or time.time() - start > 8:
                    break
            check('SSE 收到事件', len(got) > 0, str(got[:1])[:100])
    except Exception as exc:
        check('SSE 流', False, str(exc))

    print('== 静态页面 ==')
    r = get('/')
    check('GET / 返回页面', r.status_code == 200 and '<html' in r.text.lower())

    print('\n' + '=' * 60)
    print(f'通过 {len(PASS)} 项，失败 {len(FAIL)} 项')
    if FAIL:
        print('失败项：')
        for name in FAIL:
            print('  -', name)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
