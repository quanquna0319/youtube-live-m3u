# YouTube 直播 M3U 生成器

把 YouTube 上的公开直播频道整理成分门别类的 M3U 播放列表，VLC / PotPlayer / TiviMate / Kodi / 电视盒子都能直接用。

## 参考的开源项目

动手前对比了 GitHub 上几个主流方案，取长补短：

| 项目 | 做法 | 局限 |
|---|---|---|
| [benmoose39/YouTube_to_m3u](https://github.com/benmoose39/YouTube_to_m3u) | Actions 定时跑脚本，抓 `/live` 页面的 m3u8 写进 m3u | 直链 6 小时过期，静态 m3u 很快失效；分类靠人工维护 |
| [borinbilly/YT2Plex](https://github.com/borinbilly/YT2Plex) | 顺带生成 XMLTV 节目单 | 面向 Plex，配置偏重 |
| [cgomesu/youtube4tvh](https://github.com/cgomesu/youtube4tvh) | TVHeadend 插件形式把 YT 当 IPTV 频道 | 依赖 TVHeadend 环境 |
| [arapurayil/utube](https://github.com/arapurayil/utube) | Cloudflare Worker 中转 | 需要 Cloudflare 账号 |

本项目在 `YouTube_to_m3u` 的思路上改了两处关键设计：

1. **用本地代理发固定地址**，播放器里存的链接永不变，服务端每次请求时现场换成新清单，彻底绕开过期问题；
2. **生成前逐个实测**，只把真正在直播的频道写进 m3u，而不是把一堆死链丢给播放器。

## 目录结构

```
yt_m3u/
├── candidates.py        频道池（改这里就能增删频道）
├── build.py             探测 + 生成 m3u
├── proxy.py             本地代理（解决链接过期）
├── run_daemon.py        定时刷新守护
├── tools/
│   ├── verify.py        逐频道实测可播性
│   └── probe_handles.py 批量探测某个 handle 是否在播
├── out/
│   ├── youtube_live.m3u          全部频道（推荐用这个）
│   ├── youtube_live_direct.m3u   直链版（会过期，仅调试用）
│   ├── by_category/<分类>.m3u    单分类独立列表
│   └── report.json               每个频道的实测明细
└── .venv/               Python 环境（已装好 yt-dlp）
```

## 快速开始

### 1. 启动代理（必须，否则链接几小时后失效）

```bash
cd yt_m3u
./.venv/Scripts/python.exe proxy.py
```

看到 `[302 模式] 已启动 N 路直播 -> http://127.0.0.1:8899/` 即可。

浏览器打开 <http://127.0.0.1:8899/> 能看到全部频道索引，
<http://127.0.0.1:8899/player> 可以直接在网页里试播。

### 2. 播放器加载列表

把 `out/youtube_live.m3u` 拖进播放器，或者直接用地址：

```
http://127.0.0.1:8899/yt/<频道slug>.m3u8
```

频道 slug 就是频道名小写、非字母数字转横线，例如：

- `NBC News NOW` → `nbc-news-now`
- `Al Jazeera English` → `al-jazeera-english`

`out/youtube_live.m3u` 里已经写好了每个频道的这个固定地址，直接加载整个文件即可。

> 有些播放器不认 m3u 里的 http 地址，用 PotPlayer / VLC / TiviMate 都正常。
> Kodi 需要装 PVR IPTV Simple Client。

### 3. 让列表自己保持新鲜

```bash
./.venv/Scripts/python.exe run_daemon.py --interval 30
```

每 30 分钟重新探测一遍，自动剔除下播的、补进新开播的。
配合代理使用，播放器里的地址始终有效。

### 局域网共享（手机 / 电视盒子）

```bash
./.venv/Scripts/python.exe proxy.py --relay --host 0.0.0.0
```

`--relay` 会做完整中转（改写清单 + 转发分片），这样其它设备不用管出口 IP 绑定，
访问 `http://<你的电脑IP>:8899/` 即可。代价是流量过一遍本机。

## 分类一览

生成时按实测结果自动分组，当前覆盖：

| 分类 | 说明 |
|---|---|
| 新闻 | NBC / ABC / CBS / Al Jazeera / DW / Sky News / Euronews / 印度与中东多家 |
| 财经 | CNBC / Yahoo Finance / The Economic Times |
| 科技 | NASA 等 |
| 体育 | UFC / WWE / talkSPORT 等 |
| 音乐 | Lofi Girl / Chillhop 等 24 小时电台 |
| 纪录 | Discovery / Science Channel / NatGeo |
| 少儿 | Booba 等 |
| 生活 | EarthCam / 城市直播 / 天气 |

## 加自己的频道

编辑 `candidates.py`，加一行 `("频道名", "分类", "https://www.youtube.com/@handle/live")`，
然后重跑 `build.py`。不用手写 channel id —— 用 `@handle` 形式最稳，写错了会报 404 而不是静默失败。

想先确认某个频道现在是否在播：

```bash
./.venv/Scripts/python.exe tools/probe_handles.py LofiGirl NASA BBCNews
```

## 已实现与未实现

**已实测可用**
- 频道探测：49 个候选里实抓 33 个在播，覆盖 8 个分类
- 流地址：取到 HLS 主清单（6–7 档码率），逐档取子清单和分片，分片 TS 同步字节 `0x47` 校验通过
- 代理 302 模式与中转模式均验证通过
- 中文分组名加 UTF-8 BOM，Windows 播放器不乱码

**已知限制**
- 体育类直播是"事件型"的，深夜时段大部分频道不在播，这是 YouTube 本身的特性，不是脚本问题
- `@handle/live` 对某些频道会 404（频道没开过直播或已改名），脚本会跳过
- 部分频道有地区限制（如 Bloomberg 在某些地区不可用），需要代理才能看
- 直链版 `youtube_live_direct.m3u` 中的地址约 6 小时后失效，仅供排查用，日常请用代理版

## 免责

仅整理公开可访问的 YouTube 直播地址，不存储、不转播任何内容。频道的可用性、地区限制和版权均由 YouTube 与频道方决定。
