# -*- coding: utf-8 -*-
"""
前端静态自检：
1. app.js 里用到的 #id 选择器，在 index.html 中是否都存在；
2. index.html / app.js 里用到的 i18n key，中英文词条是否都齐全；
3. CSS 里被 JS 引用的 class 是否定义（提示性检查）。
"""

import os
import re
import sys

WEB = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(WEB, 'static')

html = open(os.path.join(STATIC, 'index.html'), encoding='utf-8').read()
js = open(os.path.join(STATIC, 'app.js'), encoding='utf-8').read()
css = open(os.path.join(STATIC, 'style.css'), encoding='utf-8').read()

fails = []

# ---------------------------------------------------------------- 1. id 选择器
html_ids = set(re.findall(r'\bid="([^"]+)"', html))
used_ids = set(re.findall(r"""\$\(\s*['"]#([A-Za-z0-9_-]+)""", js))
used_ids |= set(re.findall(r"""getElementById\(\s*['"]([A-Za-z0-9_-]+)['"]""", js))
# 动态生成的 id 属于运行期插入，不参与静态检查
dynamic = set(re.findall(r"""id="([A-Za-z0-9_-]+)""", js))
missing_ids = sorted(used_ids - html_ids - dynamic)
print(f'[1] HTML 中 id 共 {len(html_ids)} 个；JS 引用了 {len(used_ids)} 个')
if missing_ids:
    fails.append(f'JS 引用了不存在的 id: {missing_ids}')
    print('    [FAIL] 缺失:', missing_ids)
else:
    print('    [OK ] 全部存在')

unused = sorted(html_ids - used_ids - {'videoPlayer'})
if unused:
    print('    [info] HTML 中未被 JS 直接引用的 id:', unused)

# ---------------------------------------------------------------- 2. i18n
html_keys = set(re.findall(r'data-i18n="([^"]+)"', html))
js_keys = set(re.findall(r"""\bt\(\s*'([A-Za-z0-9_]+)'""", js))
all_keys = html_keys | js_keys

zh_start = js.index('zh: {')
en_start = js.index('en: {')
zh_block = js[zh_start:en_start]
en_block = js[en_start:js.index('\n};', en_start)]


def has_key(block, key):
    return re.search(rf'(?<![\w]){re.escape(key)}\s*:', block) is not None


missing_zh = sorted(k for k in all_keys if not has_key(zh_block, k))
missing_en = sorted(k for k in all_keys if not has_key(en_block, k))
print(f'[2] i18n key 使用 {len(all_keys)} 个（HTML {len(html_keys)} + JS {len(js_keys)}）')
if missing_zh:
    fails.append(f'中文词条缺失: {missing_zh}')
    print('    [FAIL] zh 缺失:', missing_zh)
else:
    print('    [OK ] 中文词条齐全')
if missing_en:
    fails.append(f'英文词条缺失: {missing_en}')
    print('    [FAIL] en 缺失:', missing_en)
else:
    print('    [OK ] 英文词条齐全')

# ---------------------------------------------------------------- 3. CSS 类
js_classes = set()
for match in re.findall(r"""classList\.(?:add|remove|toggle)\(([^)]*)\)""", js):
    js_classes |= set(re.findall(r"""['"]([A-Za-z0-9_-]+)['"]""", match))
for match in re.findall(r"""class="([^"]+)""", js):
    js_classes |= set(re.findall(r'[A-Za-z0-9_-]+', match))
html_classes = set()
for match in re.findall(r'class="([^"]+)"', html):
    html_classes |= set(re.findall(r'[A-Za-z0-9_-]+', match))
css_classes = set(re.findall(r'\.([A-Za-z][A-Za-z0-9_-]*)', css))

missing_css = sorted(c for c in (js_classes | html_classes) & set()
                     if c not in css_classes)
uncss = sorted((js_classes | html_classes) - css_classes)
print(f'[3] CSS 中定义了 {len(css_classes)} 个类')
if uncss:
    print('    [info] 未在 CSS 中定义（可能是工具类或拼写问题）:', uncss[:20])
else:
    print('    [OK ] 用到的类都有样式')

# ---------------------------------------------------------------- 4. 其它
if 'static/app.js' not in html or 'static/style.css' not in html:
    fails.append('index.html 未正确引入 app.js / style.css')
    print('[4] [FAIL] 静态资源引用缺失')
else:
    print('[4] [OK ] 静态资源引用正常')

print('\n' + '=' * 60)
if fails:
    for f in fails:
        print('失败:', f)
    sys.exit(1)
print('前端静态检查通过')
