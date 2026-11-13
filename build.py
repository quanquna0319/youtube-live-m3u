# -*- coding: utf-8 -*-
"""
YouTube 直播 -> M3U 生成器

用法:
    ./.venv/Scripts/python.exe build.py                # 全量刷新
    ./.venv/Scripts/python.exe build.py --workers 12   # 指定并发

产物:
    out/youtube_live.m3u        全部分类合集（播放器里按 group-title 自动分组）
    out/by_category/<分类>.m3u  单分类独立列表
    out/report.json             每个频道的实测结果
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yt_dlp

ROOT = Path(__file__).parent
OUT = ROOT / "out"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    "socket_timeout": 20,
    "retries": 2,
    # 不锁定 player_client: 强制指定会被 YouTube 判为异常客户端("page needs to be reloaded")
    "http_headers": {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
}


def m3u_safe(text: str) -> str:
    """m3u 的 EXTINF 行里逗号会截断标题, 引号会破坏属性。"""
    return text.replace(",", " ").replace('"', "'").strip()


def probe(item: tuple[str, str, str]) -> dict:
    """探测一个频道: 是否在直播 + 取 HLS 主清单地址。"""
    name, group, url = item
    rec = {"name": name, "group": group, "source": url, "ok": False,
           "live": False, "url": "", "logo": "", "error": ""}
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
        if info.get("_type") == "playlist":
            entries = [e for e in (info.get("entries") or []) if e]
            info = entries[0] if entries else {}
        if not info:
            rec["error"] = "无可用条目(频道当前未开播)"
            return rec
        if not info.get("is_live"):
            rec["error"] = "非直播内容"
            return rec

        # manifest_url 是 hls_variant 主清单, 自带多码率, 播放器可自适应
        manifest = info.get("manifest_url") or ""
        if not manifest:
            for f in (info.get("formats") or []):
                if f.get("protocol") in ("m3u8", "m3u8_native") and f.get("manifest_url"):
                    manifest = f["manifest_url"]
                    break
        if not manifest:
            rec["error"] = "未找到 HLS 清单(可能是仅 DASH 的直播)"
            return rec

        rec.update(ok=True, live=True, url=manifest,
                   logo=info.get("thumbnail") or "",
                   title=info.get("title") or "",
                   channel=info.get("channel") or info.get("uploader") or name)
    except Exception as exc:  # noqa: BLE001
        msg = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).strip()
        rec["error"] = msg.splitlines()[0][:180] if msg else exc.__class__.__name__
    return rec


def build_m3u(records: list[dict], playlist_name: str, base: str = "") -> str:
    """base 为空时写真实直链(会过期); 非空时写代理固定地址(长期有效)。"""
    lines = ['#EXTM3U', f'#PLAYLIST:{playlist_name}']
    for r in records:
        logo = f' tvg-logo="{r["logo"]}"' if r.get("logo") else ""
        lines.append(
            f'#EXTINF:-1 tvg-id="{m3u_safe(r["name"])}" tvg-name="{m3u_safe(r["name"])}"'
            f'{logo} group-title="{m3u_safe(r["group"])}",{m3u_safe(r["name"])}'
        )
        lines.append(f'#EXTVLCOPT:http-user-agent={UA}')
        if base:
            lines.append(f'{base}/{slug_of(r["name"])}.m3u8')
        else:
            lines.append(r["url"])
    return "\n".join(lines) + "\n"


def slug_of(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s or "ch"


def write_m3u(path: Path, text: str) -> None:
    """Windows 播放器常把无 BOM 的 UTF-8 误判为 GBK, 加 BOM 保证中文分组名不乱码。"""
    path.write_text(text, encoding="utf-8-sig")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8, help="并发探测数")
    ap.add_argument("--category", default="", help="只刷新某个分类(前缀匹配)")
    ap.add_argument("--proxy-base", default="http://127.0.0.1:8899/yt",
                    help="代理基地址, 用于生成长期有效的 m3u; 传空字符串则写直链")
    args = ap.parse_args()

    from candidates import CANDIDATES

    todo = [c for c in CANDIDATES if not args.category or args.category in c[1]]
    total = len(todo)
    print(f"待探测 {total} 个频道, 并发 {args.workers}\n", flush=True)

    results: list[dict] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, c): c for c in todo}
        for idx, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            results.append(rec)
            flag = "OK  " if rec["ok"] else "MISS"
            detail = rec["url"][:48] + "..." if rec["ok"] else rec["error"]
            print(f"[{idx:>3}/{total}] {flag} {rec['group']:<4} {rec['name']:<24} {detail}", flush=True)

    # 失败重试一轮: 直播页偶发抽风, 单次失败不代表频道死了
    failed = [r for r in results if not r["ok"]]
    if failed:
        print(f"\n重试 {len(failed)} 个失败项 ...", flush=True)
        src = {c[0]: c for c in todo}
        with ThreadPoolExecutor(max_workers=max(4, args.workers // 2)) as pool:
            retry = {pool.submit(probe, src[r["name"]]): r for r in failed if r["name"] in src}
            for fut in as_completed(retry):
                new = fut.result()
                if new["ok"]:
                    results = [new if r["name"] == new["name"] else r for r in results]

    alive = [r for r in results if r["ok"]]
    order = list(dict.fromkeys(c[1] for c in CANDIDATES))
    alive.sort(key=lambda r: (order.index(r["group"]) if r["group"] in order else 99, r["name"]))

    OUT.mkdir(exist_ok=True)
    (OUT / "by_category").mkdir(exist_ok=True)

    base = args.proxy_base.rstrip("/")
    write_m3u(OUT / "youtube_live.m3u", build_m3u(alive, "YouTube Live", base))
    # 直链版另存一份, 适合临时用/排查问题
    write_m3u(OUT / "youtube_live_direct.m3u", build_m3u(alive, "YouTube Live (direct)", ""))

    groups: dict[str, list[dict]] = {}
    for r in alive:
        groups.setdefault(r["group"], []).append(r)
    for gname, recs in groups.items():
        fn = OUT / "by_category" / f"{gname}.m3u"
        write_m3u(fn, build_m3u(recs, f"YouTube Live - {gname}", base))

    # 报告里不留完整直链: googlevideo 的清单是路径式参数, 里面嵌了出口 IP
    # 和临时令牌, 不该进版本库。只保留主机名便于排查。
    def redact(rec: dict) -> dict:
        out = dict(rec)
        u = out.get("url") or ""
        if u:
            parts = urllib.parse.urlsplit(u)
            out["url"] = f"{parts.scheme}://{parts.netloc}/<redacted>"
        return out

    (OUT / "report.json").write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_probed": total,
        "alive": len(alive),
        "by_group": {k: len(v) for k, v in groups.items()},
        "channels": [redact(r) for r in results],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*58}")
    print(f"在线 {len(alive)}/{total} 个频道, 耗时 {time.time()-started:.1f}s")
    for gname, recs in groups.items():
        print(f"  {gname:<6} {len(recs):>2} 个")
    print(f"输出目录: {OUT}")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
