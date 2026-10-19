# -*- coding: utf-8 -*-
"""
配置层自检（无需启动服务）：在临时副本上验证 ini 读写不会破坏原文件。

用法： python web/selftest_config.py
"""
import os
import shutil
import sys
import tempfile

WEB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WEB)

import config_store  # noqa: E402
import schema as schema_mod  # noqa: E402
import paths  # noqa: E402

PROJECT_ROOT = os.path.dirname(WEB)
SRC = os.path.join(PROJECT_ROOT, 'config', 'config.ini')
tmpdir = tempfile.mkdtemp(prefix='dlr_test_')
dst = os.path.join(tmpdir, 'config.ini')
shutil.copyfile(SRC, dst)

original = open(dst, 'rb').read()

# 1. 读取
doc = config_store.IniDocument(dst).load()
print('[1] sections:', doc.order)
print('    录制设置项数:', len(doc.values.get('录制设置', {})))
print('    Cookie项数:', len(doc.values.get('Cookie', {})))
print('    sample:', doc.get('录制设置', '视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频'))
print('    关播推送开启:', repr(doc.get('推送配置', '关播推送开启(是/否)')))

# 2. 无改动写入 -> 字节完全一致
result = config_store.update_config_file(dst, {'录制设置': {
    '视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频': 'ts',
    '循环时间(秒)': '300',
}})
print('[2] 无实际改动:', result['changed'], '| 字节一致:', open(dst, 'rb').read() == original)

# 3. 修改若干项
result = config_store.update_config_file(dst, {'录制设置': {
    '循环时间(秒)': '123',
    '是否跳过代理检测(是/否)': '是',
}, '推送配置': {
    '关播推送开启(是/否)': '是',
    '直播状态推送渠道': '钉钉, TG',
}})
after = open(dst, 'rb').read()
print('[3] 改动:', result['changed'])
print('    备份:', bool(result['backup']))
print('    BOM保留:', after[:3] == b'\xef\xbb\xbf', '| CRLF:', after.count(b'\r\n'), '| LF:', after.count(b'\n'))
text = after.decode('utf-8-sig')
print('    行数:', len(text.splitlines()), '(原', len(original.decode('utf-8-sig').splitlines()), ')')
print('    注释保留:', '# 可选微信|钉钉' in text, '| 原注释行数:',
      sum(1 for l in text.splitlines() if l.strip().startswith('#')))
doc2 = config_store.IniDocument(dst).load()
print('    读回: 循环=', doc2.get('录制设置', '循环时间(秒)'),
      '跳代理=', doc2.get('录制设置', '是否跳过代理检测(是/否)'),
      '关播=', doc2.get('推送配置', '关播推送开启(是/否)'),
      '渠道=', doc2.get('推送配置', '直播状态推送渠道'))

# 4. 新增文件中不存在的键
config_store.update_config_file(dst, {'录制设置': {'__测试新键__': 'hello'}})
doc3 = config_store.IniDocument(dst).load()
items = list(doc3.values['录制设置'].keys())
print('[4] 新键写入位置:', items[-1], '| 键总数:', len(items))
print('    值:', doc3.get('录制设置', '__测试新键__'))
print('    在段内(下一个段头之前):',
      doc3.key_index['录制设置']['__测试新键__'] < doc3.header_index['推送配置'])

# 5. schema 构建
values = config_store.read_config_values(dst)
built = schema_mod.build_schema(values)
print('[5] schema 分组:', [(s['name'], len(s['items'])) for s in built])
cookie_items = [s for s in built if s['name'] == 'Cookie'][0]['items']
print('    Cookie 示例:', [(i['key'], i['meta']['label']['zh'], i['meta']['type']) for i in cookie_items[:3]])
rec = [s for s in built if s['name'] == '录制设置'][0]['items']
odd = [i['key'] for i in rec if i['meta']['type'] == 'text'][:5]
print('    录制设置为text的键:', odd)

# 6. URL 解析
print('[6] URL 解析:')
for line in ['live.douyin.com/123', '高清, live.douyin.com/123, 小明',
             '#原画, https://live.bilibili.com/1, B站主播', 'https://a.com/x.flv']:
    e = config_store.UrlEntry(0, line)
    print(f'    {line!r} -> enabled={e.enabled} quality={e.quality!r} url={e.url!r} '
          f'name={e.name!r} valid={e.valid} to_line={e.to_line()!r}')

# 7. URL 文件读写
url_file = os.path.join(tmpdir, 'URL_config.ini')
config_store.write_url_lines(url_file, ['live.douyin.com/1', '#高清, live.bilibili.com/2, 阿B'])
print('[7] URL 文件:', repr(open(url_file, encoding='utf-8-sig').read()))
lines = config_store.read_url_lines(url_file)
lines[1] = '#原画, live.bilibili.com/2, 阿B'
config_store.write_url_lines(url_file, lines)
print('    改后:', repr(open(url_file, encoding='utf-8-sig').read()))
print('    解析:', [(i['enabled'], i['quality'], i['url'], i['name'])
                 for i in [e.to_dict() for e in config_store.read_url_file(url_file)]])

# 8. 路径解析
print('[8] save_path:', paths.resolve_save_path(PROJECT_ROOT))
print('    python:', paths.pick_python(PROJECT_ROOT))

# 9. 重复键与大小写
#    configparser 的键名大小写不敏感：同段里同时出现 SMTP邮件服务器 和 smtp邮件服务器
#    会让 main.py 抛 DuplicateOptionError 直接起不来。这里锁死相关行为。
print('[9] 重复键与大小写:')
dup_file = os.path.join(tmpdir, 'dup.ini')
with open(dup_file, 'w', encoding='utf-8-sig', newline='') as fp:
    fp.write('[推送配置]\n# 注释要保留\nsmtp邮件服务器 =\nSMTP邮件服务器 = \n其它键 = 1\n')

removed = config_store.dedupe_keys(dup_file)
dup_text = open(dup_file, encoding='utf-8-sig').read()
ok_dedupe = (removed['removed'] == 1
             and 'SMTP邮件服务器' not in dup_text
             and '# 注释要保留' in dup_text
             and '其它键 = 1' in dup_text)
print('    大小写重复键被清理:', '通过' if ok_dedupe else '失败', removed)

again = config_store.dedupe_keys(dup_file)
ok_noop = again['removed'] == 0
print('    已无重复时不再改动:', '通过' if ok_noop else '失败', again)

miss = schema_mod.missing_keys({'推送配置': {'smtp邮件服务器': '', 'SMTP邮件服务器端口': '465'}})
push_missing = miss.get('推送配置', {})
ok_case = 'SMTP邮件服务器' not in push_missing and 'SMTP邮件服务器端口' not in push_missing
print('    大小写不同不判为缺失:', '通过' if ok_case else '失败',
      f'（仍判缺失 {len(push_missing)} 个真正缺失的键）')

if not (ok_dedupe and ok_noop and ok_case):
    shutil.rmtree(tmpdir, ignore_errors=True)
    raise SystemExit('配置层自检失败：重复键 / 大小写处理有误')

shutil.rmtree(tmpdir, ignore_errors=True)
print('\n配置层自检通过')
