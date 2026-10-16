# DouyinLiveRecorder 可视化控制台

一个**零额外依赖**（只用 Python 标准库）的本地网页控制台，用来替代手工编辑
`config/config.ini` 与 `config/URL_config.ini`，并在浏览器里完成录制进程的启停与监控。

> 该目录是对原项目的**增强**，不改动原有录制逻辑：不使用控制台时，
> `python main.py` 的使用方式与之前完全一致。

---

## 1. 快速开始

### Windows

双击项目根目录的 **`启动可视化控制台.bat`** 即可，脚本会自动：
找到 Python（优先使用项目内的 `.venv`）、检测并安装缺失依赖、启动服务并打开浏览器。

### macOS / Linux

```bash
./start_web.sh
```

### 手动启动（各平台通用）

```bash
python web/server.py --open
```

启动后浏览器访问：<http://127.0.0.1:8765/>

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--port 9000` | 指定端口，默认 `8765`（被占用时自动顺延） |
| `--host 0.0.0.0` | 允许局域网访问（默认仅本机 `127.0.0.1`） |
| `--token 你的口令` | 访问需要令牌，配合 `--host` 使用 |
| `--python <路径>` | 指定用哪个 Python 解释器运行 `main.py` |
| `--open` | 启动后自动打开浏览器 |
| `--project-root <路径>` | 指定项目根目录（默认自动识别） |

---

## 2. 功能

### 界面预览

| 概览 | 直播间地址 |
| --- | --- |
| ![概览](screenshots/dashboard.png) | ![直播间地址](screenshots/urls.png) |

| 录制设置 | 推送配置 |
| --- | --- |
| ![录制设置](screenshots/config-recording.png) | ![推送配置](screenshots/config-push.png) |

| Cookie | 实时日志 |
| --- | --- |
| ![Cookie](screenshots/config-cookie.png) | ![实时日志](screenshots/logs.png) |

| 录制文件 | 深色主题 |
| --- | --- |
| ![录制文件](screenshots/files.png) | ![深色主题](screenshots/dark-dashboard.png) |

### 各页面能力

| 页面 | 能力 |
| --- | --- |
| **概览** | 运行状态、PID、运行时长、监测/录制数量、瞬时错误数、磁盘剩余空间；依赖与 ffmpeg 环境体检；一键打开保存目录；最近录制的文件 |
| **直播间地址** | 增删改查 `URL_config.ini`：画质、主播名、启用/停用（即 `#` 注释）、批量导入、批量启停；程序运行中修改会在下个循环自动生效 |
| **录制设置** | 保存路径（带目录选择器）、画质、保存格式、分段、并发线程、代理、转码、字幕、自定义脚本等全部参数 |
| **推送配置** | 推送渠道多选（微信/钉钉/TG/邮箱/BARK/ntfy/pushplus）及各渠道参数、开播/关播模板 |
| **Cookie** | 全部平台 Cookie，默认遮罩显示，聚焦即可编辑；抖音 Cookie 标注为必填 |
| **账号密码 / 授权令牌** | 需要登录的平台账号与 PopkonTV Token |
| **实时日志** | SSE 实时推送 `main.py` 的输出（含颜色分级、级别过滤、关键字过滤、暂停/清空），也可按文件查看历史日志 |
| **录制文件** | 浏览录制目录（支持子目录与搜索）、在线播放 mp4、下载（支持断点/拖动）、删除、在文件管理器中打开 |

界面细节：

* 中文 / English 一键切换（右下角 `EN` 按钮，配置项的英文标签已内置）。
* 浅色 / 深色主题切换；移动端自适应（手机浏览器也能操作）。
* 参数按类型渲染成合适的控件：开关、数字（带范围校验）、下拉、多选标签、密码、目录选择。
* **保存前会做校验**，非法值（例如给「循环时间」填字母、选择了不存在的推送渠道）会被拒绝并提示。
* 修改前自动备份到 `config/backup/`，最多保留 20 份。
* 写入配置采用「临时文件 + 原子替换」，**完整保留 `config.ini` 的注释、空行、键顺序、BOM 与换行符**。
* 地址栏带路由：`#/config/Cookie`、`#/files/D%3A%5C%E5%BD%95%E6%92%AD` 可以直接收藏或刷新回到同一页。

### 录制文件页的权限边界

![录制文件](screenshots/files.png)

* **浏览和下载不限制目录**：可以点面包屑一路点到别的盘、用工具栏的盘符下拉切换 C/D 盘，
  方便你把录制目录改到其它磁盘后仍能查看历史文件。
* **删除只允许在「录制保存路径」和项目 `downloads` 目录内**；在其它目录时，操作列不会出现删除按钮，
  并会给出提示。这是有意为之的安全边界（配合下面的接口防护）。
* 工具栏「录制目录」按钮可一键跳回配置的保存目录。

### 接口防护

控制台虽然只监听本机，但仍做了三层防护，防止别的网页在后台操纵它：

| 防护 | 说明 |
| --- | --- |
| Host 校验 | 只监听 `127.0.0.1` 时，拒绝用其它域名访问（防 DNS rebinding） |
| Origin 校验 | `Origin` 与本站不一致的请求直接 403（防 CSRF） |
| Content-Type 校验 | 只接受 `application/json`，跨站表单伪造不出合法请求 |

局域网访问（`--host 0.0.0.0`）时会自动放宽 Host 校验，此时请务必加 `--token`。

---

## 3. 对 `main.py` 的改动

为了配合控制台并修掉一个录制问题，`main.py` 只有三处改动，都做了注释，便于对照上游：

| 位置 | 改动 | 原因 |
| --- | --- | --- |
| `main.py` 全局变量区 | 新增 `headless_mode = os.environ.get('DLR_HEADLESS') == '1'` | 让控制台以子进程方式运行时能进入无交互模式 |
| `display_info()` | 无交互模式下不再执行 `cls/clear` 清屏 | 否则每秒一次的清屏会污染日志流 |
| 主循环读取直播地址处 | 无交互模式下不再调用 `input()` 等待输入 | 否则控制台启动的进程会阻塞在等待输入上 |
| `get_record_headers()` | 新增 `'B站直播': 'referer:https://live.bilibili.com/'` | **修复 B 站 403**：B 站 CDN 会校验 Referer |
| ffmpeg 参数拼接处 | B 站改用桌面版 Chrome UA | **修复 B 站 403**：安卓 UA 即使带 Referer 也会被拒（实测四种组合，只有「桌面 UA + Referer」能拉到流） |

> 不带 `DLR_HEADLESS` 时行为与原来完全一致，`python main.py` 照常提示输入地址。

---

## 4. 工作原理

```
浏览器  ──HTTP/SSE──▶  web/server.py  ──子进程──▶  python -u main.py
                          │                          （DLR_HEADLESS=1）
                          ├─ 读写 config/config.ini、config/URL_config.ini
                          ├─ 读取 logs/*.log
                          └─ 浏览 downloads/（及自定义保存目录）
```

* 控制台以子进程方式运行 `main.py`，`main.py` **本身没有被改写**，只是新增了对环境变量
  `DLR_HEADLESS=1` 的两处判断：
  1. 不再每个循环执行 `cls/clear` 清屏（否则会污染日志流）；
  2. 直播间列表为空时不再调用 `input()` 阻塞等待输入（控制台环境下会直接被拒绝启动）。
* 停止录制时会在 Windows 上结束整棵进程树（`taskkill /T /F`），避免 `ffmpeg` 变成孤儿进程。
  ⚠️ 强制结束可能损坏正在写入的文件，建议把「视频保存格式」设为 `ts`。
* 未做任何内网穿透；默认只监听 `127.0.0.1`。

---

## 5. 目录结构

```
web/
├── server.py           # 本地 HTTP 服务 + REST/SSE 接口（标准库实现）
├── config_store.py     # ini 无损读写、URL 列表解析
├── schema.py           # 每个配置项的控件元数据（类型/标签/说明/选项）
├── process_manager.py  # main.py 子进程管理、日志缓冲、状态解析、环境体检
├── files_api.py        # 录制文件浏览/下载/删除（含路径穿越防护）
├── paths.py            # 路径解析（项目根、保存目录、解释器选择）
├── static/             # 前端（原生 HTML/CSS/JS，无构建步骤）
│   ├── index.html
│   ├── style.css
│   └── app.js
├── selftest_config.py  # 配置层自检
├── selftest_api.py     # 接口自检
├── selftest_frontend.py# 前端静态自检（选择器 / 多语言词条）
├── selftest_e2e.py     # 端到端自检（真实启停 main.py）
└── devtools_screenshot.py # 开发辅助：无头浏览器给各页面截图
```

---

## 6. 自检

启动控制台后（默认 8765 端口），另开一个终端：

```bash
python web/selftest_config.py            # 配置读写（无需启动服务）
python web/selftest_frontend.py          # 前端静态检查（无需启动服务）
python web/selftest_api.py --port 8765   # 40 项接口测试
python web/selftest_e2e.py --port 8765   # 真实启动/停止 main.py 子进程
```

`selftest_e2e.py` 会临时新增一个无效直播间地址、启动进程、观察日志后停止并删除测试数据，
不会破坏你的配置。

修改前端后想确认页面渲染是否正常，可以按上面的截图方式复查（需要 Chrome/Edge 与
`pip install websocket-client`）：

```bash
python web/devtools_screenshot.py --port 8765 --out web/screenshots
```

---

## 7. 常见问题

**Q：点「启动录制」提示缺少依赖包？**
控制台会检测用于运行 `main.py` 的解释器。请在项目目录执行
`pip install -r requirements.txt`，或把依赖装进项目内的 `.venv`（控制台会优先使用它）。

**Q：提示未检测到 ffmpeg？**
Windows 可执行 `winget install Gyan.FFmpeg`，或自行下载后把 `ffmpeg.exe` 放到项目根目录
的 `ffmpeg` 文件夹（`main.py` 会自动把它加入 `PATH`）。

**Q：端口被占用？**
默认 8765，被占用时自动顺延；也可用 `--port` 指定。

**Q：关掉控制台窗口，录制会停吗？**
会。录制进程是控制台的子进程，请在网页上先点「停止」。若只关窗口，
`main.py` 可能继续在后台运行，此时可用任务管理器结束 `python.exe`（注意也会结束其 `ffmpeg`）。

**Q：会覆盖我手工写的 `config.ini` 注释吗？**
不会。控制台按行修改，只替换对应键的值，注释、顺序、空行、编码都会保留。

**Q：想让局域网内其它设备访问？**
`python web/server.py --host 0.0.0.0 --token 你的口令`，
然后访问 `http://你的内网IP:8765/?token=你的口令`。请注意控制台可以启停录制、删除文件，
务必设置令牌并只在可信网络中使用。

**Q：B 站录制报 `Server returned 403 Forbidden`？**
已修复（见第 3 节的 `get_record_headers` 与 UA 改动）。注意 **`main.py` 的修改必须重启录制进程才生效**：
在网页上点「重启」，或先「停止」再「启动」。

**Q：改完「直播保存路径」需要重启吗？**
不需要。保存路径是 `main.py` 每轮循环重新读取的，下一个循环就会用新路径；
已经在录的那条会继续写到旧路径。文件页也会立刻切到新目录。

**Q：为什么有些目录里看不到删除按钮？**
当前目录不在「录制保存路径」和项目 `downloads` 之内。这是有意的安全边界，
只影响删除，浏览和下载不受限制。

**Q：录制中的文件能删吗？**
不建议。正在写入的文件被删除后 `ffmpeg` 仍持有句柄，可能持续占用或报错。
先「停止」再删。

**Q：换了保存磁盘后，怎么快速跳到新目录看文件？**
文件页工具栏的盘符下拉可以切 C/D 盘，点面包屑的任意一层也能跳；
「录制目录」按钮一键回到配置的保存目录。
