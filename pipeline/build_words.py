#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 KyleBing/english-vocabulary 的托福词表里筛出「偏重点」3000 词。

思路：托福 13,477 词 − 初中/高中已学词 = 真正需要背的进阶词；
顺序沿用原表顺序（该表按重要性/频率排过），取前 N 个。
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
APP = r"E:\2026\toefl-app"


def load_words(txt_path):
    out = set()
    if not os.path.exists(txt_path):
        return out
    for line in open(txt_path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        w = re.split(r"[\s\t,，]", line)[0].strip().lower()
        if w and re.fullmatch(r"[a-z][a-z'\-]*", w):
            out.add(w)
    return out


def main():
    raw = json.load(open(os.path.join(HERE, "_toefl-raw.json"), encoding="utf-8"))
    junior = load_words(os.path.join(HERE, "junior.txt"))
    senior = load_words(os.path.join(HERE, "senior.txt"))
    basic = junior | senior
    print(f"托福 {len(raw)} 条；初中 {len(junior)} / 高中 {len(senior)} / 合计基础 {len(basic)}")

    seen, picked = set(), []
    for rec in raw:
        w = (rec.get("word") or "").strip().lower()
        if not w or w in seen:
            continue
        if not re.fullmatch(r"[a-z][a-z'\-]*", w):
            continue
        if w in basic:
            continue
        tr = rec.get("translations") or []
        if not tr:
            continue
        pos = tr[0].get("type") or ""
        zh = "；".join(f"{t.get('translation','').strip()}" for t in tr[:3] if t.get("translation"))
        if not zh:
            continue
        ph = ""
        phz = ""
        phs = rec.get("phrases") or []
        for p in phs:
            if p.get("phrase") and p.get("translation"):
                ph, phz = p["phrase"], p["translation"]
                break
        seen.add(w)
        picked.append({"w": w, "pos": pos, "zh": zh[:80], "ph": ph[:60], "phz": phz[:60]})

    print(f"筛掉基础词后剩 {len(picked)} 个")
    N = 3000
    picked = picked[:N]
    out = {
        "meta": {
            "count": len(picked),
            "source": "KyleBing/english-vocabulary (TOEFL) minus 初中/高中",
            "note": "顺序沿用原表，越靠前越常见/越该先背",
        },
        "words": picked,
    }
    path = os.path.join(APP, "data", "words.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"写入 {path}（{os.path.getsize(path)/1024:.0f} KB）")
    print("前 10:", [x["w"] for x in picked[:10]])
    print("后 5 :", [x["w"] for x in picked[-5:]])


if __name__ == "__main__":
    main()
