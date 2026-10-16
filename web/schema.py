# -*- coding: utf-8 -*-

"""
DouyinLiveRecorder 可视化控制台 - 配置项元数据

把 config.ini 里的「中文键名」映射成网页上的控件：
类型（开关 / 数字 / 下拉 / 多选 / 密码 / 目录 / 文本域）、中英文标签、说明、取值范围。

没有在这里登记的键不会被丢弃：会自动推断类型并显示在对应分组里，
因此上游 main.py 以后新增配置项时，本页面无需修改即可编辑。
"""

import re

LANG = ('zh', 'en')

# --------------------------------------------------------------------- 分组
SECTIONS = [
    {
        'name': '录制设置',
        'label': {'zh': '录制设置', 'en': 'Recording'},
        'desc': {
            'zh': '保存路径、画质、分段、并发线程等核心录制参数',
            'en': 'Save path, quality, segmenting, concurrency and other core options',
        },
        'icon': 'video',
    },
    {
        'name': '推送配置',
        'label': {'zh': '推送配置', 'en': 'Notifications'},
        'desc': {'zh': '开播/关播消息推送渠道与内容', 'en': 'Push channels and message templates'},
        'icon': 'bell',
    },
    {
        'name': 'Cookie',
        'label': {'zh': 'Cookie', 'en': 'Cookies'},
        'desc': {
            'zh': '各平台 Cookie，录制抖音必填；填写后部分平台才能拿到高清源',
            'en': 'Per-platform cookies. Douyin cookie is required.',
        },
        'icon': 'cookie',
    },
    {
        'name': '账号密码',
        'label': {'zh': '账号密码', 'en': 'Accounts'},
        'desc': {'zh': '需要登录的平台账号', 'en': 'Accounts for platforms that require login'},
        'icon': 'user',
    },
    {
        'name': 'Authorization',
        'label': {'zh': '授权令牌', 'en': 'Authorization'},
        'desc': {'zh': '第三方平台访问令牌', 'en': 'Third-party access tokens'},
        'icon': 'key',
    },
]

QUALITY_OPTIONS = ['原画', '蓝光', '超清', '高清', '标清', '流畅']
FORMAT_OPTIONS = ['ts', 'mkv', 'flv', 'mp4', 'mp3音频', 'm4a音频']
PUSH_CHANNELS = ['微信', '钉钉', 'TG', '邮箱', 'BARK', 'NTFY', 'PUSHPLUS']

PROXY_PLATFORM_SUGGESTIONS = [
    'tiktok', 'soop', 'pandalive', 'winktv', 'flextv', 'popkontv', 'twitch', 'liveme',
    'showroom', 'chzzk', 'shopee', 'shp', 'youtu', 'faceit', 'picarto', 'migu',
]

# --------------------------------------------------------------------- 字段
# type: bool | int | float | text | textarea | secret | select | multiselect | list | path
FIELDS = {
    '录制设置': {
        'language(zh_cn/en)': dict(
            type='select', options=['zh_cn', 'en'], default='zh_cn',
            label={'zh': '控制台语言', 'en': 'Console language'},
            help={'zh': '影响 main.py 命令行输出语言', 'en': 'Language of the console output of main.py'},
        ),
        '是否跳过代理检测(是/否)': dict(
            type='bool', default='否',
            label={'zh': '跳过代理检测', 'en': 'Skip proxy detection'},
            help={'zh': '开启后启动时不检测系统代理，可加快启动', 'en': 'Skip the system proxy probe at startup'},
        ),
        '直播保存路径(不填则默认)': dict(
            type='path', default='', placeholder='例如 D:\\live-recordings',
            label={'zh': '直播保存路径', 'en': 'Save path'},
            help={'zh': '留空则保存到项目下的 downloads 目录', 'en': 'Empty = ./downloads'},
        ),
        '保存文件夹是否以作者区分': dict(type='bool', default='是', label={'zh': '按作者分文件夹', 'en': 'Folder per author'}),
        '保存文件夹是否以时间区分': dict(type='bool', default='否', label={'zh': '按日期分文件夹', 'en': 'Folder per date'}),
        '保存文件夹是否以标题区分': dict(type='bool', default='否', label={'zh': '按标题分文件夹', 'en': 'Folder per title'}),
        '保存文件名是否包含标题': dict(type='bool', default='否', label={'zh': '文件名含标题', 'en': 'Title in filename'}),
        '是否去除名称中的表情符号': dict(type='bool', default='是', label={'zh': '去除名称中的表情', 'en': 'Strip emoji from names'}),
        '视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频': dict(
            type='select', options=FORMAT_OPTIONS, default='ts',
            label={'zh': '视频保存格式', 'en': 'Output format'},
            help={'zh': '推荐 ts：异常中断时不易损坏文件', 'en': 'ts is recommended: survives interruption'},
        ),
        '原画|超清|高清|标清|流畅': dict(
            type='select', options=QUALITY_OPTIONS, default='原画',
            label={'zh': '录制画质', 'en': 'Recording quality'},
            help={'zh': '默认画质；也可在每个直播间地址前单独指定', 'en': 'Default quality; can be overridden per URL'},
        ),
        '是否使用代理ip(是/否)': dict(
            type='bool', default='是',
            label={'zh': '使用代理 IP', 'en': 'Use proxy'},
            help={'zh': '海外平台通常需要', 'en': 'Usually required for overseas platforms'},
        ),
        '代理地址': dict(
            type='text', default='', placeholder='http://127.0.0.1:7890',
            label={'zh': '代理地址', 'en': 'Proxy address'},
        ),
        '同一时间访问网络的线程数': dict(
            type='int', default=3, min=1, max=50,
            label={'zh': '并发线程数', 'en': 'Concurrent threads'},
            help={'zh': '同一时间访问网络的线程数', 'en': 'Threads hitting the network at once'},
        ),
        '循环时间(秒)': dict(
            type='int', default=300, min=5,
            label={'zh': '循环检测间隔(秒)', 'en': 'Loop interval (s)'},
        ),
        '排队读取网址时间(秒)': dict(
            type='int', default=0, min=0,
            label={'zh': '读取网址排队间隔(秒)', 'en': 'URL queue delay (s)'},
        ),
        '是否显示循环秒数': dict(type='bool', default='否', label={'zh': '显示循环秒数', 'en': 'Show loop countdown'}),
        '是否显示直播源地址': dict(type='bool', default='否', label={'zh': '显示直播源地址', 'en': 'Show stream URL'}),
        '分段录制是否开启': dict(type='bool', default='是', label={'zh': '开启分段录制', 'en': 'Enable segmenting'}),
        '是否强制启用https录制': dict(type='bool', default='否', label={'zh': '强制 https 录制', 'en': 'Force https'}),
        '录制空间剩余阈值(gb)': dict(
            type='float', default=1.0, min=0, step=0.5,
            label={'zh': '磁盘剩余阈值(GB)', 'en': 'Free disk threshold (GB)'},
            help={'zh': '剩余空间低于该值时停止录制', 'en': 'Stop recording below this free space'},
        ),
        '视频分段时间(秒)': dict(
            type='int', default=1800, min=60, step=60,
            label={'zh': '分段时间(秒)', 'en': 'Segment length (s)'},
        ),
        '录制完成后自动转为mp4格式': dict(type='bool', default='是', label={'zh': '录完转 mp4', 'en': 'Convert to mp4'}),
        'mp4格式重新编码为h264': dict(
            type='bool', default='否',
            label={'zh': 'mp4 重新编码为 h264', 'en': 'Re-encode mp4 to h264'},
            help={'zh': '更兼容但会明显增加耗时', 'en': 'More compatible, much slower'},
        ),
        '追加格式后删除原文件': dict(type='bool', default='是', label={'zh': '转码后删除原文件', 'en': 'Delete source after convert'}),
        '生成时间字幕文件': dict(type='bool', default='否', label={'zh': '生成时间字幕文件', 'en': 'Generate subtitle file'}),
        '是否录制完成后执行自定义脚本': dict(type='bool', default='否', label={'zh': '录完执行自定义脚本', 'en': 'Run custom script'}),
        '自定义脚本执行命令': dict(
            type='text', default='', depends_on='是否录制完成后执行自定义脚本',
            label={'zh': '自定义脚本命令', 'en': 'Custom script command'},
        ),
        '使用代理录制的平台(逗号分隔)': dict(
            type='list', default='tiktok, sooplive, pandalive, winktv, flextv, popkontv, twitch, liveme, showroom, chzzk, shopee, shp, youtu',
            suggestions=PROXY_PLATFORM_SUGGESTIONS,
            label={'zh': '走代理的平台', 'en': 'Platforms using proxy'},
        ),
        '额外使用代理录制的平台(逗号分隔)': dict(
            type='list', default='', suggestions=PROXY_PLATFORM_SUGGESTIONS,
            label={'zh': '额外走代理的平台', 'en': 'Extra platforms using proxy'},
        ),
    },
    '推送配置': {
        '直播状态推送渠道': dict(
            type='multiselect', options=PUSH_CHANNELS, default='',
            label={'zh': '推送渠道', 'en': 'Push channels'},
            help={'zh': '可多选，留空表示不推送', 'en': 'Multiple allowed; empty = disabled'},
        ),
        '钉钉推送接口链接': dict(type='text', default='', label={'zh': '钉钉机器人 Webhook', 'en': 'DingTalk webhook'}),
        '微信推送接口链接': dict(type='text', default='', label={'zh': '微信推送接口', 'en': 'WeChat push URL'}),
        'bark推送接口链接': dict(type='text', default='', label={'zh': 'Bark 推送地址', 'en': 'Bark URL'}),
        'bark推送中断级别': dict(
            type='select', options=['active', 'timeSensitive', 'passive', 'critical'], default='active',
            label={'zh': 'Bark 中断级别', 'en': 'Bark level'},
        ),
        'bark推送铃声': dict(type='text', default='bell', label={'zh': 'Bark 铃声', 'en': 'Bark sound'}),
        '钉钉通知@对象(填手机号)': dict(type='text', default='', label={'zh': '钉钉 @手机号', 'en': 'DingTalk @phone'}),
        '钉钉通知@全体(是/否)': dict(type='bool', default='否', label={'zh': '钉钉 @全体成员', 'en': 'DingTalk @all'}),
        'tgapi令牌': dict(type='secret', default='', label={'zh': 'Telegram Bot Token', 'en': 'Telegram bot token'}),
        'tg聊天id(个人或者群组id)': dict(type='text', default='', label={'zh': 'Telegram Chat ID', 'en': 'Telegram chat id'}),
        'SMTP邮件服务器': dict(type='text', default='', label={'zh': 'SMTP 服务器', 'en': 'SMTP server'}),
        '是否使用SMTP服务SSL加密(是/否)': dict(type='bool', default='是', label={'zh': 'SMTP 使用 SSL', 'en': 'SMTP over SSL'}),
        'SMTP邮件服务器端口': dict(type='int', default=465, min=1, max=65535, label={'zh': 'SMTP 端口', 'en': 'SMTP port'}),
        '邮箱登录账号': dict(type='text', default='', label={'zh': '邮箱登录账号', 'en': 'Mail account'}),
        '发件人密码(授权码)': dict(type='secret', default='', label={'zh': '邮箱授权码', 'en': 'Mail auth code'}),
        '发件人邮箱': dict(type='text', default='', label={'zh': '发件人邮箱', 'en': 'Sender address'}),
        '发件人显示昵称': dict(type='text', default='', label={'zh': '发件人昵称', 'en': 'Sender name'}),
        '收件人邮箱': dict(
            type='text', default='', label={'zh': '收件人邮箱', 'en': 'Recipient'},
            help={'zh': '多个用英文逗号分隔', 'en': 'Comma separated'},
        ),
        'ntfy推送地址': dict(type='text', default='https://ntfy.sh/xxxx', label={'zh': 'ntfy 推送地址', 'en': 'ntfy URL'}),
        'ntfy推送标签': dict(type='text', default='tada', label={'zh': 'ntfy 标签', 'en': 'ntfy tags'}),
        'ntfy推送邮箱': dict(type='text', default='', label={'zh': 'ntfy 邮箱', 'en': 'ntfy email'}),
        'pushplus推送token': dict(type='secret', default='', label={'zh': 'pushplus token', 'en': 'pushplus token'}),
        '自定义推送标题': dict(type='text', default='直播间状态更新通知', label={'zh': '推送标题', 'en': 'Push title'}),
        '自定义开播推送内容': dict(
            type='textarea', default='', rows=3,
            label={'zh': '开播推送内容', 'en': 'Live-start template'},
            help={'zh': '留空使用默认模板', 'en': 'Empty = default template'},
        ),
        '自定义关播推送内容': dict(
            type='textarea', default='', rows=3,
            label={'zh': '关播推送内容', 'en': 'Live-end template'},
        ),
        '只推送通知不录制(是/否)': dict(
            type='bool', default='否', label={'zh': '只推送不录制', 'en': 'Notify only'},
            help={'zh': '开启后仅检测开播状态并推送，不保存视频', 'en': 'Detect and notify without recording'},
        ),
        '直播推送检测频率(秒)': dict(type='int', default=1800, min=30, label={'zh': '推送检测频率(秒)', 'en': 'Push check interval (s)'}),
        '开播推送开启(是/否)': dict(type='bool', default='是', label={'zh': '开播推送', 'en': 'Notify on live start'}),
        '关播推送开启(是/否)': dict(type='bool', default='否', label={'zh': '关播推送', 'en': 'Notify on live end'}),
    },
    '账号密码': {
        'sooplive账号': dict(type='text', default='', label={'zh': 'SOOP 账号', 'en': 'SOOP account'}),
        'sooplive密码': dict(type='secret', default='', label={'zh': 'SOOP 密码', 'en': 'SOOP password'}),
        'flextv账号': dict(type='text', default='', label={'zh': 'FlexTV 账号', 'en': 'FlexTV account'}),
        'flextv密码': dict(type='secret', default='', label={'zh': 'FlexTV 密码', 'en': 'FlexTV password'}),
        'popkontv账号': dict(type='text', default='', label={'zh': 'PopkonTV 账号', 'en': 'PopkonTV account'}),
        'partner_code': dict(type='text', default='P-00001', label={'zh': 'PopkonTV partner_code', 'en': 'PopkonTV partner_code'}),
        'popkontv密码': dict(type='secret', default='', label={'zh': 'PopkonTV 密码', 'en': 'PopkonTV password'}),
        'twitcasting账号类型': dict(
            type='select', options=['normal', 'premium'], default='normal',
            label={'zh': 'TwitCasting 账号类型', 'en': 'TwitCasting account type'},
        ),
        'twitcasting账号': dict(type='text', default='', label={'zh': 'TwitCasting 账号', 'en': 'TwitCasting account'}),
        'twitcasting密码': dict(type='secret', default='', label={'zh': 'TwitCasting 密码', 'en': 'TwitCasting password'}),
    },
    'Authorization': {
        'popkontv_token': dict(type='secret', default='', label={'zh': 'PopkonTV Token', 'en': 'PopkonTV token'}),
    },
}

# Cookie 段：键 -> 平台中文名
COOKIE_PLATFORM_NAMES = {
    '抖音cookie': '抖音',
    '快手cookie': '快手',
    'tiktok_cookie': 'TikTok',
    '虎牙cookie': '虎牙',
    '斗鱼cookie': '斗鱼',
    'yy_cookie': 'YY',
    'b站cookie': 'B站',
    '小红书cookie': '小红书',
    'bigo_cookie': 'Bigo',
    'blued_cookie': 'Blued',
    'sooplive_cookie': 'SOOP',
    'netease_cookie': '网易CC',
    '千度热播_cookie': '千度热播',
    'pandatv_cookie': 'PandaTV',
    '猫耳fm_cookie': '猫耳FM',
    'winktv_cookie': 'WinkTV',
    'flextv_cookie': 'FlexTV',
    'look_cookie': 'Look',
    'twitcasting_cookie': 'TwitCasting',
    'baidu_cookie': '百度',
    'weibo_cookie': '微博',
    'kugou_cookie': '酷狗',
    'twitch_cookie': 'Twitch',
    'liveme_cookie': 'LiveMe',
    'huajiao_cookie': '花椒',
    'liuxing_cookie': '流星',
    'showroom_cookie': 'ShowRoom',
    'acfun_cookie': 'AcFun',
    'changliao_cookie': '畅聊',
    'yinbo_cookie': '音播',
    'yingke_cookie': '映客',
    'zhihu_cookie': '知乎',
    'chzzk_cookie': 'CHZZK',
    'haixiu_cookie': '嗨秀',
    'vvxqiu_cookie': 'VV星球',
    '17live_cookie': '17Live',
    'langlive_cookie': '浪Live',
    'pplive_cookie': '漂漂',
    '6room_cookie': '六间房',
    'lehaitv_cookie': '乐嗨',
    'huamao_cookie': '花猫',
    'shopee_cookie': 'Shopee',
    'youtube_cookie': 'YouTube',
    'taobao_cookie': '淘宝',
    'jd_cookie': '京东',
    'faceit_cookie': 'Faceit',
    'migu_cookie': '咪咕',
    'lianjie_cookie': '连接',
    'laixiu_cookie': '来秀',
    'picarto_cookie': 'Picarto',
}

# 需要重点提示的平台
COOKIE_REQUIRED = {'抖音cookie'}

_SECRET_HINTS = ('密码', 'password', 'token', '密钥', '授权码', 'secret')
_TEXTAREA_HINTS = ('cookie', 'cookie:')
_INT_HINTS = ('(秒)', '(gb)', '线程数', '端口')


def guess_type(key: str, value: str = '') -> str:
    """未登记的键：根据名字/取值推断控件类型。"""
    lowered = key.lower()
    if '(是/否)' in key or key.startswith('是否') or key.startswith('启用'):
        return 'bool'
    if any(hint in lowered for hint in _SECRET_HINTS) or '密码' in key:
        return 'secret'
    if 'cookie' in lowered:
        return 'secret'
    if '|' in key:
        return 'select'
    if ',' in key and '逗号' in key:
        return 'list'
    if any(hint in lowered for hint in _INT_HINTS):
        return 'int'
    if isinstance(value, str) and len(value) > 60:
        return 'textarea'
    return 'text'


def field_meta(section: str, key: str, value: str = '') -> dict:
    meta = dict(FIELDS.get(section, {}).get(key, {}))
    if not meta:
        meta['type'] = guess_type(key, value)
    meta.setdefault('type', 'text')
    meta.setdefault('default', '')

    if 'label' not in meta:
        if section == 'Cookie':
            platform = COOKIE_PLATFORM_NAMES.get(key)
            if not platform:
                platform = re.sub(r'[_\s]*cookie$', '', key, flags=re.IGNORECASE)
            meta['label'] = {'zh': platform, 'en': platform}
        else:
            meta['label'] = {'zh': key, 'en': key}
    else:
        meta['label'].setdefault('en', meta['label'].get('zh', key))

    meta.setdefault('help', {})
    if key in COOKIE_REQUIRED:
        meta['required'] = True
        meta['help'].setdefault('zh', '录制抖音必填，从浏览器开发者工具复制完整 Cookie')
        meta['help'].setdefault('en', 'Required for Douyin. Paste the full cookie from DevTools.')
    if section == 'Cookie':
        meta.setdefault('rows', 2)
    meta.setdefault('key', key)
    meta.setdefault('section', section)
    return meta


def build_schema(config_values: dict) -> list:
    """把「配置文件里的实际内容」+「元数据」组装成前端需要的结构。

    以配置文件中的顺序为准，保证网页顺序与 config.ini 一致；
    同时补齐配置文件中缺失、但元数据里登记过的键。
    """
    result = []
    known = {s['name']: s for s in SECTIONS}
    section_names = [name for name in config_values.keys()]
    # 保证常用分组始终存在，且顺序稳定
    for name in known:
        if name not in section_names:
            section_names.append(name)

    for name in section_names:
        values = config_values.get(name, {})
        items = []
        used = set()
        for key, value in values.items():
            meta = field_meta(name, key, value)
            items.append({'key': key, 'value': value, 'meta': meta})
            used.add(key)
        for key, raw_meta in FIELDS.get(name, {}).items():
            if key in used:
                continue
            default = raw_meta.get('default', '')
            meta = field_meta(name, key, default)
            items.append({'key': key, 'value': default, 'meta': meta, 'absent': True})
        info = known.get(name, {})
        result.append({
            'name': name,
            'label': info.get('label', {'zh': name, 'en': name}),
            'desc': info.get('desc', {'zh': '', 'en': ''}),
            'icon': info.get('icon', 'settings'),
            'items': items,
        })
    return result
