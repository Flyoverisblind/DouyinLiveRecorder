# -*- coding: utf-8 -*-
"""
端到端自检：真实启动 main.py 子进程，验证启停、日志流、状态解析。

用法： python web/selftest_e2e.py --port 8799
"""

import argparse
import sys
import time

import requests

TEST_URL = 'https://live.douyin.com/999999999999'
FAIL = []


def check(name, ok, detail=''):
    print(f'  [{"OK " if ok else "FAIL"}] {name}' + (f' -> {detail}' if detail else ''))
    if not ok:
        FAIL.append(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8799)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    base = f'http://{args.host}:{args.port}'

    def get(p, **kw):
        return requests.get(base + p, timeout=30, **kw)

    def post(p, payload=None):
        return requests.post(base + p, json=payload or {}, timeout=90)

    print('== 准备：确保进程未运行 ==')
    st = get('/api/state').json()
    if st['process']['running']:
        post('/api/control/stop')
        time.sleep(3)
    check('初始状态为未运行', not get('/api/state').json()['process']['running'])

    print('== 添加测试用直播间地址 ==')
    post('/api/urls/delete', {'indexes': [i['index'] for i in get('/api/urls').json()['items']]})
    r = post('/api/urls', {'url': TEST_URL, 'quality': '原画', 'name': '端到端自检'})
    check('添加成功', r.status_code == 200, str(r.json().get('error', ''))[:80])

    print('== 启动录制进程 ==')
    r = post('/api/control/start')
    check('启动接口返回成功', r.status_code == 200, str(r.json())[:120])
    pid = r.json().get('pid')
    check('返回了 PID', bool(pid), str(pid))
    time.sleep(2)
    st = get('/api/state').json()
    check('状态变为运行中', st['process']['running'], f"pid={st['process']['pid']}")
    check('解释器为项目 .venv', '.venv' in st['app']['python'], st['app']['python'])

    print('== 观察实时日志（15 秒）==')
    since = 0
    all_entries, stats = [], {}
    deadline = time.time() + 15
    while time.time() < deadline:
        data = get('/api/logs/snapshot', params={'since': since}).json()
        for entry in data['items']:
            all_entries.append(entry)
            since = max(since, entry['id'])
        st = get('/api/state').json()
        stats = st['process']['stats']
        time.sleep(1.5)
    check('捕获到子进程输出', len(all_entries) > 0, f'{len(all_entries)} 行')
    texts = [e['text'] for e in all_entries]
    joined = '\n'.join(texts)
    check('出现版本号 Banner', 'DouyinLiveRecorder' in joined or '版本号' in joined)
    check('无 ANSI 转义乱码', '\x1b' not in joined)
    check('未出现交互式 input 提示', '请输入要录制的主播直播间网址' not in joined)
    print('     -------- 日志样例（最多 14 行）--------')
    for line in texts[:14]:
        print('     |', line[:150])
    print('     ---------------------------------------')

    print('== 日志 SSE 增量 ==')
    try:
        with requests.get(base + '/api/logs/stream', stream=True, timeout=15) as resp:
            got = 0
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith('data:'):
                    got += 1
                if got >= 2:
                    break
            check('SSE 至少收到 2 个事件', got >= 2, f'{got} 个')
    except Exception as exc:
        check('SSE 增量', False, str(exc))

    print('== 停止录制进程 ==')
    r = post('/api/control/stop')
    check('停止接口返回成功', r.status_code == 200, str(r.json())[:120])
    time.sleep(2)
    st = get('/api/state').json()
    check('状态变为已停止', not st['process']['running'])
    check('记录了退出码', st['process']['exit_code'] is not None, str(st['process']['exit_code']))
    last = get('/api/logs/snapshot').json()['items'][-3:]
    check('退出日志已写入', any('退出' in e['text'] for e in last),
          ' / '.join(e['text'][:40] for e in last))

    print('== 清理测试数据 ==')
    r = post('/api/urls/delete', {'indexes': [i['index'] for i in get('/api/urls').json()['items']
                                             if '999999999999' in i['url']]})
    check('删除测试地址', r.status_code == 200)

    print('\n' + '=' * 60)
    if FAIL:
        print('失败项：', FAIL)
        return 1
    print('端到端测试全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
