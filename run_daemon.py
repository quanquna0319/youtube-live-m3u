# -*- coding: utf-8 -*-
"""
定时刷新守护 —— 让 m3u 里的频道列表长期可用

YouTube 直播是事件型的: 频道会开播/下播, 直链 6 小时过期。
本脚本每隔 N 分钟重跑一次 build.py, 自动剔除已下播、补入新开播的频道。

用法:
    ./.venv/Scripts/python.exe run_daemon.py                 # 默认 30 分钟
    ./.venv/Scripts/python.exe run_daemon.py --interval 15   # 15 分钟
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
PY = sys.executable


def one_round(proxy_base: str) -> tuple[int, int]:
    ts = time.strftime("%H:%M:%S")
    print(f"\n[{ts}] 开始刷新 ...", flush=True)
    t0 = time.time()
    r = subprocess.run([PY, str(ROOT / "build.py"), "--workers", "6",
                        "--proxy-base", proxy_base],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"在线 (\d+)/(\d+)", out)
    alive, total = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    print(f"[{ts}] 完成: 在线 {alive}/{total}, 耗时 {time.time()-t0:.1f}s", flush=True)
    return alive, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=30, help="刷新间隔(分钟)")
    ap.add_argument("--proxy-base", default="http://127.0.0.1:8899/yt")
    args = ap.parse_args()

    print(f"守护启动, 每 {args.interval} 分钟刷新一次。Ctrl+C 退出。", flush=True)
    while True:
        try:
            one_round(args.proxy_base)
        except Exception as exc:  # noqa: BLE001
            print(f"本轮失败: {exc}", flush=True)
        try:
            time.sleep(args.interval * 60)
        except KeyboardInterrupt:
            print("\n已退出")
            return 0


if __name__ == "__main__":
    sys.exit(main())
