#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把当天的 TOEFL 简报发到 QQ（通过本机桥接 127.0.0.1:3010）。

用法：
  python notify_qq.py           # 发今天的
  python notify_qq.py --dry     # 只打印不发送
"""
import json
import os
import sys
import urllib.request
from datetime import date

APP = r"E:\2026\toefl-app"
BRIDGE = "http://127.0.0.1:3010/send"
SITE = "https://hinawihako.github.io/toefl-daily/"


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main(dry=False):
    news = load(os.path.join(APP, "data", "news", "index.json"), [])
    items = news if isinstance(news, list) else news.get("items", [])
    if not items:
        print("没有新闻，跳过")
        return 1

    lines = [f"📰 TOEFL 每日 · {date.today().isoformat()}", ""]
    for i, it in enumerate(items[:9], 1):
        title = (it.get("title_en") or "").strip()
        cat = it.get("category") or ""
        lines.append(f"{i}. [{cat}] {title}")
    lines.append("")
    lines.append(f"详情与音频：{SITE}")

    audio_dir = os.path.join(APP, "data", "audio")
    mp3 = None
    if os.path.isdir(audio_dir):
        today = date.today().isoformat()
        cand = os.path.join(audio_dir, f"{today}-briefing.mp3")
        if os.path.exists(cand):
            mp3 = cand

    text = "\n".join(lines)
    if dry:
        print(text)
        print("\n附件:", mp3)
        return 0

    payload = {"text": text}
    if mp3:
        payload["file"] = mp3
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(BRIDGE, data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("已发送:", r.read().decode()[:200])
        return 0
    except Exception as e:
        print("发送失败:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main(dry="--dry" in sys.argv))
