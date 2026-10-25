#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为 data/words.json 里每个词生成发音 mp3（edge-tts，可断点续跑）。"""
import asyncio
import json
import os
import sys

import edge_tts

APP = r"E:\2026\toefl-app"
OUT = os.path.join(APP, "data", "audio", "words")
VOICE = "en-US-JennyNeural"
CONCURRENCY = 4


async def one(word, sem, stats):
    path = os.path.join(OUT, word + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 800:
        stats["skip"] += 1
        return
    async with sem:
        for attempt in range(3):
            try:
                c = edge_tts.Communicate(word, VOICE, rate="-5%")
                await c.save(path)
                if os.path.getsize(path) > 800:
                    stats["ok"] += 1
                    return
            except Exception:
                await asyncio.sleep(1 + attempt)
        stats["fail"] += 1
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


async def main():
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(os.path.join(APP, "data", "words.json"), encoding="utf-8"))
    words = [w["w"] for w in data["words"]]
    sem = asyncio.Semaphore(CONCURRENCY)
    stats = {"ok": 0, "skip": 0, "fail": 0}
    tasks = [one(w, sem, stats) for w in words]
    done = 0
    for chunk_start in range(0, len(tasks), 100):
        chunk = tasks[chunk_start:chunk_start + 100]
        await asyncio.gather(*chunk)
        done += len(chunk)
        print(f"{done}/{len(tasks)}  ok={stats['ok']} skip={stats['skip']} fail={stats['fail']}", flush=True)
    total = len([f for f in os.listdir(OUT) if f.endswith('.mp3')])
    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith('.mp3')) / 1048576
    print(f"DONE files={total} size={size:.1f}MB fail={stats['fail']}")


if __name__ == "__main__":
    asyncio.run(main())
