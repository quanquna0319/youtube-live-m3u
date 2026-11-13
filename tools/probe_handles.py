# -*- coding: utf-8 -*-
"""快速批量探测一组 handle, 只打印在线的。"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

OPTS = {"quiet": True, "no_warnings": True, "skip_download": True,
        "socket_timeout": 15, "retries": 1}

handles = [h.strip() for h in sys.argv[1:] if h.strip()]


def one(h):
    url = f"https://www.youtube.com/@{h}/live"
    try:
        with yt_dlp.YoutubeDL(OPTS) as y:
            info = y.extract_info(url, download=False)
        if info.get("_type") == "playlist":
            es = [e for e in (info.get("entries") or []) if e]
            info = es[0] if es else {}
        if info.get("is_live") and (info.get("manifest_url") or any(
                f.get("manifest_url") for f in info.get("formats") or [])):
            return h, "LIVE", (info.get("title") or "")[:60]
        return h, "no", "非直播"
    except Exception as e:
        m = str(e).splitlines()[0]
        for k in ("The channel is not currently live", "does not exist", "404"):
            if k in m:
                return h, "no", k
        return h, "no", m[:70]


t = time.time()
with ThreadPoolExecutor(max_workers=6) as p:
    for h, st, msg in p.map(one, handles):
        print(f"{st:<5} {h:<26} {msg}", flush=True)
print(f"-- {len(handles)} 个, {time.time()-t:.1f}s")
