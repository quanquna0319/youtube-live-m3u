# -*- coding: utf-8 -*-
"""逐频道实测: 通过代理取清单 -> 子清单 -> 首个分片, 校验 TS 同步字节。"""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
B = "http://127.0.0.1:8899"


def get(u, t=45):
    return op.open(u, timeout=t).read()


def slug(n):
    return re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-").lower()


def check(c):
    try:
        m = get(f"{B}/yt/{slug(c['name'])}.m3u8").decode()
        first = [l for l in m.splitlines() if l.startswith("https://")][0]
        sub = get(first).decode()
        seg = [l for l in sub.splitlines() if l.startswith("https://")][0]
        d = get(seg)
        if d[:1] == b"\x47" and len(d) > 1000:
            return c["name"], True, f"{len(d)}B"
        return c["name"], False, "分片异常"
    except Exception as e:  # noqa: BLE001
        return c["name"], False, str(e)[:70]


lst = [c for c in json.loads(get(B + "/channels.json")) if c["ok"]]
print(f"待验证 {len(lst)} 路\n", flush=True)
ok = 0
fails = []
with ThreadPoolExecutor(max_workers=5) as p:
    for name, good, info in p.map(check, lst):
        print(("OK   " if good else "FAIL ") + f"{name:<26} {info}", flush=True)
        ok += good
        if not good:
            fails.append(name)
print(f"\n结果: 可播 {ok}/{len(lst)}", flush=True)
if fails:
    print("失败:", ", ".join(fails), flush=True)
