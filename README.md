<div align="center">

# DouyinLiveRecorder · 二次修改版

**本仓库是 [ihmily/DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) 的二次修改（二改）版本**

在原项目基础上，新增了一个零依赖的网页版可视化控制台，并修复了 B 站录制 403 的问题。

<a href="web/screenshots/dashboard.png"><img src="web/screenshots/dashboard.png" width="880" alt="网页控制台"></a>

</div>

---

## 📌 关于本项目（二改声明）

|  |  |
| --- | --- |
| **来源** | 修改自 [ihmily/DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder)，原作者 **Hmily** |
| **性质** | **二次修改版本**。除下面「本版改动」列出的内容外，其余录制逻辑均来自原项目 |
| **授权** | 沿用原项目的 **MIT 协议**，原版权归 Hmily 所有，详见 [LICENSE](LICENSE) |
| **维护范围** | 本仓库只维护修改部分。**原项目本身的问题（某平台录不了、接口失效等）请到[上游仓库反馈](https://github.com/ihmily/DouyinLiveRecorder/issues)**，我这边不保证跟进 |
| **需要原版？** | 如果你想要原作者的打包版 exe、官方 Docker 镜像等，请访问[上游仓库](https://github.com/ihmily/DouyinLiveRecorder) |

> 一句话：**代码主要是上游的，网页控制台是本仓库加的。** 项目原有的功能与支持的平台没有削减。

## ✨ 本版改动

| 改动 | 说明 |
| --- | --- |
| 🖥️ **新增网页版可视化控制台** | 浏览器里改参数、管直播间、启停录制、看实时日志、管理录制文件。只用 Python 标准库实现，**不引入任何新依赖** |
| 🐛 **修复 B 站录制 403** | 上游版本用安卓 UA 且不带 Referer，B 站 CDN 会直接返回 403。本版改用桌面版 UA 并补上 Referer（实测四种组合，只有「桌面 UA + Referer」能拿到流） |
| 🔧 **main.py 增加无交互模式** | 由控制台以子进程方式启动时（环境变量 `DLR_HEADLESS=1`），不再每秒清屏、不再阻塞在 `input()`。不带这个变量时行为与上游完全一致 |

对 `main.py` 的具体改动位置见 [web/README.md](web/README.md#4-对-mainpy-的改动)。

## 🖥️ 网页版可视化控制台

在浏览器里完成原本需要手工编辑 `config.ini` 的全部操作：

| 页面 | 能做什么 |
| --- | --- |
| **概览** | 运行状态、PID、运行时长、监测/录制数量、瞬时错误、磁盘剩余；依赖与 ffmpeg 体检 |
| **直播间地址** | 增删改查、画质、主播名、启用/停用、批量导入 |
| **录制设置 / 推送配置 / Cookie / 账号密码** | `config.ini` 全部参数，按类型渲染成开关/数字/下拉/多选/密码/目录选择 |
| **实时日志** | SSE 实时推送，级别与关键字过滤，也可查看历史日志文件 |
| **录制文件** | 浏览、在线播放、下载（支持拖动/断点）、删除，可跨盘浏览；多选后**无损合并**或**裁掉黑边转 16:9** |

其它：中文/English 切换、深浅主题、手机浏览器可用、改配置自动备份、保存前做合法性校验。

**Windows**：双击项目根目录的 `启动可视化控制台.bat`，浏览器会自动打开。

> 这是**前台**方式：控制台跑在这个窗口里，**关掉窗口就等于关掉控制台**（和 `web/README.md` 里说明的一致）。

**想让控制台在后台常驻**（关掉启动窗口也不影响网页）：双击 `启动控制台_后台.bat`，
它用 `pythonw.exe` 把控制台完全脱离出去启动，窗口可以随手关掉；要停止时双击 `停止控制台_后台.bat`
（会先让网页端优雅停止录制，再结束整个进程树，避免留下孤儿 `main.py`）。

**macOS / Linux**：

```bash
./start_web.sh
```

**手动运行（各平台通用）**，然后访问 <http://127.0.0.1:8765/>：

```bash
python web/server.py --open
```

> 控制台默认只监听 `127.0.0.1`。如需局域网访问请用 `--host 0.0.0.0 --token 你的口令`。
> 完整说明、命令行参数与常见问题见 **[web/README.md](web/README.md)**。

## 😺 已支持平台

抖音 / TikTok / 快手 / 虎牙 / 斗鱼 / YY / B站 / 小红书 / bigo / blued / SOOP(原AfreecaTV) /
网易CC / 千度热播 / PandaTV / 猫耳FM / Look / WinkTV / FlexTV(TTingLive) / PopkonTV / TwitCasting /
百度 / 微博 / 酷狗 / Twitch / LiveMe / 花椒 / 流星 / ShowRoom / Acfun / 映客 / 音播 / 知乎 / CHZZK /
嗨秀 / VV星球 / 17Live / 浪Live / 畅聊 / 飘飘 / 六间房 / 乐嗨 / 花猫 / Shopee / Youtube / 淘宝 / 京东 /
Faceit / 咪咕 / 连接 / 来秀 / Picarto

## 🚀 快速开始

### 1. 获取代码

```bash
git clone https://github.com/Flyoverisblind/DouyinLiveRecorder.git
cd DouyinLiveRecorder
```

### 2. 安装依赖

需要 **Python >= 3.10**。推荐用虚拟环境：

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
```

> 国内下载慢可以加镜像源：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 3. 安装 FFmpeg

**Windows**：一般可跳过（程序会尝试自动安装，把 `ffmpeg.exe` 放到项目根目录的 `ffmpeg` 文件夹即可）。
也可以 `winget install Gyan.FFmpeg`。

**CentOS**：

```bash
yum install epel-release && yum install ffmpeg
```

**Ubuntu / Debian**：

```bash
apt update && apt install ffmpeg
```

**macOS**：

```bash
brew install ffmpeg
```

### 4. 运行

**方式一：网页控制台（推荐）**

```bash
python web/server.py --open     # 或直接双击 启动可视化控制台.bat
```

在网页的「直播间地址」里添加直播间，然后点「启动录制」。

**方式二：命令行**

在 `config/URL_config.ini` 里一行一个直播间地址，然后：

```bash
python main.py          # Linux/macOS 用 python3 main.py
```

录制的视频保存在 `downloads` 文件夹（可在配置里改成别的路径）。

## ⚙️ 配置说明

配置文件都在 `config/` 目录下：

- **`URL_config.ini`** —— 要录制的直播间地址，一行一个。
  行首加 `#` 表示暂时不录制这个直播间。
- **`config.ini`** —— 录制参数、推送渠道、各平台 Cookie 等，**推荐用网页控制台修改**（会自动备份到 `config/backup/`，并保留原有注释）。

几个要点：

- 默认录制清晰度为 `原画`。想单独指定某个直播间的画质，写成 `画质, 地址` 的形式，例如
  `超清, https://live.douyin.com/745964462470`（中间要有逗号）。
- **推荐把保存格式设为 `ts`**：即使被强制中断，已录制的部分也不容易损坏。
- 长时间挂机循环监测时，循环时间建议设长一点，避免请求过于频繁被平台限制。
- 要停止录制，可以在网页上点「停止」，Windows 也可以运行 `StopRecording.vbs`，或在命令行按 `Ctrl+C`。
- 录制 TikTok 等海外平台需要开启代理并在配置里填写代理地址（如 `127.0.0.1:7890`）。
- 录制抖音需要填 `Cookie` 里的抖音 cookie（网页上「Cookie」页可以直接粘贴）。

### 直播间地址示例

```
抖音:
https://live.douyin.com/745964462470
https://v.douyin.com/iQFeBnt/
https://live.douyin.com/yall1102          （链接+抖音号）
https://v.douyin.com/CeiU5cbX             （主播主页地址）

TikTok:
https://www.tiktok.com/@pearlgaga88/live

快手:
https://live.kuaishou.com/u/yall1102

虎牙:
https://www.huya.com/52333

斗鱼:
https://www.douyu.com/3637778?dyshid=

YY:
https://www.yy.com/22490906/22490906

B站:
https://live.bilibili.com/320

小红书（直播间分享地址):
http://xhslink.com/xpJpfM

bigo:
https://www.bigo.tv/cn/716418802

blued:
https://app.blued.cn/live?id=Mp6G2R

SOOP:
https://play.sooplive.co.kr/sw7love

网易cc:
https://cc.163.com/583946984

千度热播:
https://qiandurebo.com/web/video.php?roomnumber=33333

PandaTV:
https://www.pandalive.co.kr/live/play/bara0109

猫耳FM:
https://fm.missevan.com/live/868895007

Look:
https://look.163.com/live?id=65108820&position=3

WinkTV:
https://www.winktv.co.kr/live/play/anjer1004

FlexTV(TTingLive):
https://www.flextv.co.kr/channels/593127/live

PopkonTV:
https://www.popkontv.com/live/view?castId=wjfal007&partnerCode=P-00117

TwitCasting:
https://twitcasting.tv/c:uonq

百度:
https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377&tab_category

微博:
https://weibo.com/l/wblive/p/show/1022:2321325026370190442592

酷狗:
https://fanxing2.kugou.com/50428671

Twitch:
https://www.twitch.tv/gamerbee

LiveMe:
https://www.liveme.com/zh/v/17141543493018047815/index.html

花椒:
https://www.huajiao.com/l/345096174

流星:
https://www.7u66.com/100960

ShowRoom:
https://www.showroom-live.com/room/profile?room_id=480206   （主播主页地址）

Acfun:
https://live.acfun.cn/live/179922

映客:
https://www.inke.cn/liveroom/index.html?uid=22954469&id=1720860391070904

音播:
https://live.ybw1666.com/800002949

知乎:
https://www.zhihu.com/people/ac3a467005c5d20381a82230101308e9   （主播主页地址）

CHZZK:
https://chzzk.naver.com/live/458f6ec20b034f49e0fc6d03921646d2

嗨秀:
https://www.haixiutv.com/6095106

VV星球:
https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html?h5Server=https://h5p.vvxqiu.com&roomId=LP115924473&platformId=vvstar

17Live:
https://17.live/en/live/6302408

浪Live:
https://www.lang.live/en-US/room/3349463

畅聊:
https://live.tlclw.com/106188

飘飘:
https://m.pp.weimipopo.com/live/preview.html?uid=91648673&anchorUid=91625862&app=plpl

六间房:
https://v.6.cn/634435

乐嗨:
https://www.lehaitv.com/8059096

花猫:
https://h.catshow168.com/live/preview.html?uid=19066357&anchorUid=18895331

Shopee:
https://sg.shp.ee/GmpXeuf?uid=1006401066&session=802458

Youtube:
https://www.youtube.com/watch?v=cS6zS5hi1w0

淘宝（需 cookie）:
https://tbzb.taobao.com/live?liveId=532359023188

京东:
https://3.cn/28MLBy-E

Faceit:
https://www.faceit.com/zh/players/Compl1/stream

连接:
https://show.lailianjie.com/10000258

咪咕:
https://www.miguvideo.com/p/live/120000541321

来秀:
https://www.imkktv.com/h5/share/video.html?uid=1845195&roomId=1710496

Picarto:
https://www.picarto.tv/cuteavalanche
```

## 🐋 容器运行

需要先装好 [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)。

> ⚠️ 上游的官方镜像 `ihmily/douyin-live-recorder` **不包含本仓库新增的网页控制台**。
> 想在容器里用控制台，请按下面第 2 步本地构建镜像。

1. **在容器内运行前，先编辑好 `config/URL_config.ini`**（或在控制台界面里添加）。
2. 修改 `docker-compose.yaml`：把 `#build: .` 的注释去掉，并把 `image:` 改成自己的名字，例如：

   ```yaml
   image: douyin-live-recorder:latest
   build: .
   ```

3. 构建并启动：

   ```bash
   docker-compose up -d
   ```

4. 查看日志 / 停止：

   ```bash
   docker-compose logs -f
   docker-compose down
   ```

> ⚠️ **不要在容器运行中直接中断**，否则正在录制的视频文件可能损坏。
> 请在网页上点「停止」，或先等当前录制结束。无论哪种运行方式，都推荐使用 `ts` 格式保存。

## 📁 目录结构

```
DouyinLiveRecorder/
├── config/                  # config.ini（参数）、URL_config.ini（直播间地址）
├── downloads/               # 默认录制保存目录
├── logs/                    # 运行日志
├── src/                     # 各平台直播间信息与直播流地址解析
├── web/                     # 本仓库新增：网页版可视化控制台
│   ├── server.py            # 本地 HTTP 服务 + REST/SSE 接口（标准库实现）
│   ├── config_store.py      # ini 无损读写
│   ├── schema.py            # 配置项的控件元数据
│   ├── process_manager.py   # main.py 子进程管理与日志缓冲
│   ├── files_api.py         # 录制文件浏览/下载/删除
│   ├── media_tools.py       # 多段无损合并、裁黑边转 16:9
│   ├── media_jobs.py        # 后处理任务队列（进度 / 取消）
│   ├── static/              # 前端（原生 HTML/CSS/JS，无构建步骤）
│   └── README.md            # 控制台详细说明
├── main.py                  # 录制主程序
├── msg_push.py              # 直播状态推送
├── ffmpeg_install.py        # ffmpeg 安装脚本
├── src/javascript/          # 部分平台需要的解密脚本
├── index.html               # 播放 m3u8 / flv 的网页
├── 启动可视化控制台.bat       # Windows 前台启动（关窗口即退出控制台）
├── 启动控制台_后台.bat        # Windows 后台常驻启动（关窗口不影响网页）
├── 停止控制台_后台.bat        # 停止后台控制台（先停录制再结束进程树）
└── start_web.sh             # macOS / Linux 启动控制台
```

## ❓ 常见问题

**Q：控制台提示缺少依赖包 / 未检测到 ffmpeg？**
控制台启动时会体检。依赖未装：`pip install -r requirements.txt`（放进项目内 `.venv` 会被优先使用）。
缺 ffmpeg：见上面第 3 步。

**Q：网页上改了「直播保存路径」，需要重启吗？**
不需要，下一个循环就会用新路径；已经在录的那条会继续写到旧路径。

**Q：关掉控制台窗口后，网页就提示 `127.0.0.1 拒绝连接`？**
`启动可视化控制台.bat` 是**前台**方式，控制台就是那个窗口里的进程，关窗口它就被结束了。
想关窗口还能用网页，改用 `启动控制台_后台.bat`（`pythonw.exe` 完全脱离启动），
停止时用 `停止控制台_后台.bat`。详见 [web/README.md](web/README.md#1-快速开始)。

**Q：明明还有窗口开着，为什么 8765 打不开？**
可能启动了多个实例：端口被占用时控制台会自动顺延到 8766、8767…，
请以窗口里打印的地址为准（后台方式还会把地址记在 `logs/console.pid` 第 2 行）。

**Q：为什么有些目录里看不到删除按钮？**
当前目录不在「录制保存路径」和项目 `downloads` 之内。这是有意的安全边界，浏览和下载不受限制。

**Q：B 站以前报 403，现在还会吗？**
本版已修复。注意修改的是 `main.py`，**需要重启录制进程才生效**。

**Q：某平台的录制失败了 / 接口失效了？**
那属于上游逻辑问题，请到[上游仓库](https://github.com/ihmily/DouyinLiveRecorder/issues)反馈或等待上游更新。
本仓库只维护网页控制台和上面列出的改动。

更多问答见 [web/README.md](web/README.md#8-常见问题)。

## ⚠️ 免责声明

- 本项目仅供**个人学习与技术研究**使用，请勿用于任何商业用途或非法用途。
- 请遵守各直播平台的服务条款与相关法律法规，**不要录制、传播侵权或违法内容**。
- 请尊重主播与版权方，录制内容请勿二次传播或用于盈利。
- 使用本工具产生的一切后果由使用者自行承担，作者与贡献者不承担任何责任。
- 本项目为二次修改版本，与原作者无关；原作者不对本仓库的任何改动负责。

## 📄 许可证

本项目沿用 **[MIT License](LICENSE)**，原始版权归 **Hmily** 所有（Copyright (c) 2025 Hmily）。
根据 MIT 协议，本仓库保留原始版权声明与许可证全文。二次修改部分的改动同样以 MIT 协议发布。

---

<div align="center">

原项目：<https://github.com/ihmily/DouyinLiveRecorder> · 本仓库：<https://github.com/Flyoverisblind/DouyinLiveRecorder>

</div>
