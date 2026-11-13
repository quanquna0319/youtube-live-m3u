# -*- coding: utf-8 -*-
"""
YouTube 直播本地代理 —— 解决 m3u 链接过期问题

YouTube 的 HLS 主清单带 expire / ip 参数, 约 6 小时失效且绑定出口 IP。
本服务对外暴露固定地址 http://127.0.0.1:8899/yt/<slug>.m3u8
每次请求时现场解析最新清单:
  - 默认 302 跳转到最新 manifest (无中转开销, 播放器直连 Google CDN)
  - --relay 模式做完整中转, 改写清单与分片, 局域网其它设备也能看

用法:
    ./.venv/Scripts/python.exe proxy.py              # 302 模式
    ./.venv/Scripts/python.exe proxy.py --relay      # 中转模式
    ./.venv/Scripts/python.exe proxy.py --port 9000
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yt_dlp

ROOT = Path(__file__).parent
OUT = ROOT / "out"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

OPTS = {"quiet": True, "no_warnings": True, "skip_download": True,
        "socket_timeout": 25, "retries": 2,
        "http_headers": {"User-Agent": UA}}

# 清单缓存: slug -> (manifest_url, 取到的时间)
_cache: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 240  # 秒, 远小于 YouTube 的 6 小时有效期


def slug_of(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s or "ch"


PLAYER_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube 直播播放器</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js"></script>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,"Microsoft YaHei",sans-serif;background:#0f1115;color:#e8ecf2;
display:flex;height:100vh;overflow:hidden}
#side{width:280px;flex:0 0 280px;background:#161a21;overflow-y:auto;border-right:1px solid #232a34}
#side h1{font-size:14px;padding:16px 16px 8px;margin:0;color:#8b97a8;font-weight:600;
letter-spacing:.5px}
.grp{padding:10px 16px 4px;font-size:12px;color:#5f6b7d;text-transform:uppercase}
.ch{padding:9px 16px;font-size:13.5px;cursor:pointer;border-left:3px solid transparent;
display:flex;align-items:center;gap:8px}
.ch:hover{background:#1d2330}
.ch.on{background:#1d2a3d;border-left-color:#3b82f6;color:#fff}
.dot{width:6px;height:6px;border-radius:50%;background:#2f3945;flex:0 0 6px}
.dot.live{background:#2ecc71;box-shadow:0 0 6px #2ecc71}
#main{flex:1;display:flex;flex-direction:column;min-width:0}
#bar{padding:12px 18px;background:#161a21;border-bottom:1px solid #232a34;font-size:14px}
#bar b{color:#fff}
video{flex:1;width:100%;background:#000;min-height:0}
#msg{padding:10px 18px;font-size:13px;color:#8b97a8;background:#161a21;min-height:38px}
#msg.err{color:#ff8a80}
</style></head><body>
<div id="side"><h1>YouTube 直播 · <span id="cnt">0</span> 路</h1></div>
<div id="main">
  <div id="bar">请选择左侧频道</div>
  <video id="v" controls autoplay playsinline></video>
  <div id="msg">就绪</div>
</div>
<script>
const v=document.getElementById('v'),msg=document.getElementById('msg'),
bar=document.getElementById('bar'),side=document.getElementById('side');
let hls=null,cur=null;
function slug(n){return (n.replace(/[^A-Za-z0-9]+/g,'-').replace(/^-|-$/g,'').toLowerCase())||'ch';}
function setMsg(t,e){msg.textContent=t;msg.className=e?'err':'';}
fetch('/channels.json').then(r=>r.json()).then(list=>{
  document.getElementById('cnt').textContent=list.filter(c=>c.ok).length;
  const groups={};
  list.forEach(c=>{(groups[c.group]=groups[c.group]||[]).push(c);});
  for(const g in groups){
    const h=document.createElement('div');h.className='grp';h.textContent=g;side.appendChild(h);
    groups[g].forEach(c=>{
      const d=document.createElement('div');d.className='ch';
      d.innerHTML='<span class="dot'+(c.ok?' live':'')+'"></span>'+c.name;
      d.onclick=()=>play(c,d);side.appendChild(d);
    });
  }
});
function play(c,el){
  document.querySelectorAll('.ch').forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  bar.innerHTML='<b>'+c.name+'</b> · '+c.group;
  setMsg('正在解析直播流 ...');
  const src='/yt/'+slug(c.name)+'.m3u8';
  if(hls){hls.destroy();hls=null;}
  v.removeAttribute('src');v.load();
  if(window.Hls&&Hls.isSupported()){
    hls=new Hls({lowLatencyMode:true,liveSyncDurationCount:3});
    hls.loadSource(src);hls.attachMedia(v);
    hls.on(Hls.Events.MANIFEST_PARSED,()=>{v.play().catch(()=>{});setMsg('播放中');});
    hls.on(Hls.Events.ERROR,(e,data)=>{
      if(data.fatal){setMsg('播放失败: '+data.details+' (频道可能已下播)',1);}
    });
  }else{
    v.src=src;v.play().catch(()=>{});
  }
}
</script></body></html>"""


def load_channels() -> list[dict]:
    """读取全部频道（含当前不在播的）。

    代理是现场解析的，所以把离线频道也保留：频道一开播，播放器刷新即可用，
    不必等下一轮 build.py。
    """
    f = OUT / "report.json"
    if not f.exists():
        raise SystemExit("请先运行 build.py 生成 out/report.json")
    data = json.loads(f.read_text(encoding="utf-8"))
    recs = data["channels"]
    # 在线的排前面，方便索引页阅读
    recs.sort(key=lambda c: (not c.get("ok"), c.get("group", ""), c.get("name", "")))
    return recs


def resolve(source_url: str) -> str:
    """现场解析频道当前直播的主清单地址。"""
    with yt_dlp.YoutubeDL(OPTS) as ydl:
        info = ydl.extract_info(source_url, download=False)
    if info.get("_type") == "playlist":
        es = [e for e in (info.get("entries") or []) if e]
        info = es[0] if es else {}
    if not info.get("is_live"):
        raise RuntimeError("频道当前未直播")
    m = info.get("manifest_url") or ""
    if not m:
        for f in info.get("formats") or []:
            if f.get("manifest_url"):
                m = f["manifest_url"]
                break
    if not m:
        raise RuntimeError("未找到 HLS 清单")
    return m


def cached_manifest(slug: str, source_url: str) -> str:
    now = time.time()
    with _cache_lock:
        hit = _cache.get(slug)
        if hit and now - hit[1] < CACHE_TTL:
            return hit[0]
    m = resolve(source_url)
    with _cache_lock:
        _cache[slug] = (m, now)
    return m


def http_get(url: str, timeout: int = 25) -> tuple[int, bytes, str]:
    """拉取上游资源。先直连; 直连失败再尝试系统代理。"""
    last = None
    for handler in (urllib.request.ProxyHandler({}),
                    urllib.request.ProxyHandler()):
        try:
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=timeout) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last  # type: ignore[misc]


def enc(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def dec(token: str) -> str:
    return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()


def rewrite_playlist(text: str, slug: str) -> str:
    """把清单里的绝对/相对地址都改写成中转地址。"""
    out_lines = []
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out_lines.append(f"/yt/{slug}/p?u={enc(s)}")
        elif "#EXT-X-MEDIA:" in s or "#EXT-X-KEY:" in s:
            def sub(mt: re.Match) -> str:
                return f'{mt.group(1)}"/yt/{slug}/p?u={enc(mt.group(2))}"'
            s = re.sub(r'(URI=)"([^"]+)"', sub, s)
            out_lines.append(s)
        else:
            out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def make_handler(channels: dict[str, dict], relay: bool):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):  # 静音, 避免刷屏
            pass

        def _send(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)

            if path == "/":
                self._send(200, self._index().encode(), "text/html; charset=utf-8")
                return

            if path == "/player":
                self._send(200, PLAYER_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return

            if path == "/channels.json":
                self._send(200, json.dumps(list(channels.values()),
                                           ensure_ascii=False).encode(),
                           "application/json")
                return

            m = re.match(r"^/yt/([^/]+)\.m3u8$", path)
            if m:
                slug = m.group(1)
                ch = channels.get(slug)
                if not ch:
                    self._send(404, b"unknown channel")
                    return
                try:
                    master = cached_manifest(slug, ch["source"])
                except Exception as exc:  # noqa: BLE001
                    self._send(502, f"resolve failed: {exc}".encode())
                    return
                if not relay:
                    self.send_response(302)
                    self.send_header("Location", master)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                try:
                    _, body, _ = http_get(master)
                except Exception as exc:  # noqa: BLE001
                    self._send(502, f"fetch failed: {exc}".encode())
                    return
                self._send(200, rewrite_playlist(body.decode("utf-8", "replace"), slug).encode(),
                           "application/vnd.apple.mpegurl")
                return

            if path.startswith("/yt/") and path.endswith("/p"):
                token = (qs.get("u") or [""])[0]
                if not token:
                    self._send(400, b"missing u")
                    return
                try:
                    target = dec(token)
                except Exception:  # noqa: BLE001
                    self._send(400, b"bad token")
                    return
                try:
                    status, body, ctype = http_get(target)
                except Exception as exc:  # noqa: BLE001
                    self._send(502, f"upstream failed: {exc}".encode())
                    return
                slug = path.split("/")[2]
                if target.split("?")[0].endswith(".m3u8") or b"#EXTM3U" in body[:64]:
                    self._send(200, rewrite_playlist(body.decode("utf-8", "replace"), slug).encode(),
                               "application/vnd.apple.mpegurl")
                else:
                    # 分片直接原样回传
                    self.send_response(200)
                    self.send_header("Content-Type", ctype or "video/mp2t")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                return

            self._send(404, b"not found")

        def _index(self) -> str:
            rows = "\n".join(
                f'<li><b>{c["name"]}</b> <span class="tag">{c["group"]}</span>'
                f'<br><a href="/yt/{s}.m3u8">/yt/{s}.m3u8</a></li>'
                for s, c in channels.items())
            mode = "中转模式" if relay else "302 模式"
            return f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>YouTube 直播代理 · {mode}</title>
<style>body{{font-family:system-ui,"Microsoft YaHei";max-width:760px;margin:40px auto;
padding:0 20px;color:#222;line-height:1.7}}
h1{{font-size:20px}}ul{{padding-left:18px}}li{{margin:12px 0}}
a{{color:#0b62d6;font-size:13px;word-break:break-all}}
.tag{{background:#eef2f7;border-radius:4px;padding:1px 7px;font-size:12px;color:#456}}
code{{background:#f4f6f8;padding:2px 6px;border-radius:4px}}</style>
<h1>YouTube 直播代理（{mode}）· {len(channels)} 路</h1>
<p>把下面任一条地址加进播放器（VLC / PotPlayer / TiviMate / Kodi）即可，地址长期固定。</p>
<ul>{rows}</ul></html>"""

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--relay", action="store_true", help="完整中转, 局域网可共享")
    args = ap.parse_args()

    recs = load_channels()
    channels = {slug_of(c["name"]): c for c in recs}

    host = "0.0.0.0" if args.relay else args.host
    srv = ThreadingHTTPServer((host, args.port), make_handler(channels, args.relay))
    mode = "中转模式" if args.relay else "302 模式"
    print(f"[{mode}] 已启动 {len(channels)} 路直播 -> http://{args.host}:{args.port}/")
    print(f"  总列表: http://{args.host}:{args.port}/  (浏览器打开看索引)")
    print("  Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
