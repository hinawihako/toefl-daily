#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TOEFL 每日 · 新闻管线：RSS → 摘要/翻译/生词（本地 LLM）→ 听力音频（edge-tts）→ 静态 JSON。

用法：
  python run_daily.py                # 抓取 + 生成今天的新闻和音频
  python run_daily.py --no-tts       # 只生成文本
  python run_daily.py --limit 3      # 只处理 3 条（调试）
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) toefl-daily/1.0"


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_feed(xml_bytes, feed):
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"  [warn] RSS 解析失败 {feed['name']}: {e}", file=sys.stderr)
        return out
    items = root.iter("item")
    if not list(root.iter("item")):
        items = root.iter("{http://www.w3.org/2005/Atom}entry")
    for it in items:
        def t(tag, alt=None):
            el = it.find(tag)
            if el is None and alt:
                el = it.find(alt)
            return strip_tags(el.text if el is not None and el.text else "")
        link = t("link")
        if not link:
            le = it.find("{http://www.w3.org/2005/Atom}link")
            if le is not None:
                link = le.get("href") or ""
        title = t("title")
        desc = t("description") or t("summary", "{http://www.w3.org/2005/Atom}summary")
        if not title:
            continue
        out.append({
            "feed": feed["name"], "category": feed["category"],
            "title": title, "summary": desc[:900], "link": link,
        })
    return out


def llm_chat(messages, cfg):
    """按 endpoints 顺序尝试，每条重试 retries 次，全失败才抛错。"""
    last = None
    for ep in cfg["endpoints"]:
        for attempt in range(1, cfg.get("retries", 2) + 1):
            body = json.dumps({
                "model": ep["model"], "messages": messages,
                "temperature": cfg.get("temperature", 0.3),
                "max_tokens": cfg.get("max_tokens", 1200), "stream": False,
            }).encode("utf-8")
            req = urllib.request.Request(
                ep["base_url"].rstrip("/") + "/chat/completions", data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer local"})
            try:
                with urllib.request.urlopen(req, timeout=cfg.get("timeout", 300)) as r:
                    data = json.loads(r.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last = e
                print(f"      [try {ep['name']} #{attempt}] {str(e)[:70]}", file=sys.stderr)
                import time as _t
                _t.sleep(2)
    raise RuntimeError(f"all LLM endpoints failed: {last}")


SYS = """You are an English teacher preparing a TOEFL reading lesson from a news item.
Return ONLY minified JSON, no markdown fences, matching:
{"title_en":"<rewritten clear headline>",
 "summary_en":["<2-3 sentences, B2 level, plain English>"],
 "key_points_en":["<3 short bullet facts>"],
 "translation_zh":["<faithful Chinese translation of summary, same sentence count>"],
 "vocab":[{"word":"<1-2 word collocation from the text>","zh":"<Chinese meaning in context>"}],
 "category":"<finance|ai|tech|policy>",
 "tags":["<2-4 lowercase tags>"]}
Rules: 4-5 vocab items, all really appear in the text; no proper nouns in vocab; no extra keys."""


def json_from(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no json")
    return json.loads(m.group(0))


def summarize(item, cfg):
    user = (f"Source: {item['feed']} ({item['category']})\n"
            f"Headline: {item['title']}\n"
            f"Excerpt: {item['summary'][:700]}\n\nMake the lesson JSON.")
    raw = llm_chat([{"role": "system", "content": SYS},
                    {"role": "user", "content": user}], cfg)
    data = json_from(raw)
    data["id"] = re.sub(r"[^a-z0-9]+", "-", (data.get("title_en", "") or item["title"]).lower())[:48].strip("-")
    data["source"] = item["feed"]
    data["link"] = item["link"]
    for k in ("summary_en", "key_points_en", "translation_zh", "vocab", "tags"):
        data.setdefault(k, [])
    return data


def make_audio(items, out_mp3, cfg):
    """把当天新闻压成一段 60-90 秒听力稿，用 edge-tts 合成。"""
    import asyncio
    import edge_tts
    lines = ["Here is your daily briefing."]
    for it in items[:4]:
        for s in it.get("summary_en", [])[:1]:
            lines.append(s)
    script = " ".join(lines)
    if len(script) > cfg["max_chars"]:
        script = script[:cfg["max_chars"]].rsplit(" ", 1)[0] + "."
    async def go():
        c = edge_tts.Communicate(script, cfg["voice"], rate=cfg["rate"])
        await c.save(out_mp3)
    asyncio.run(go())
    return script


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=CFG["max_items"])
    ap.add_argument("--no-tts", action="store_true")
    args = ap.parse_args()

    out_dir = os.path.join(CFG["out"]["app_dir"], CFG["out"]["news_dir"])
    aud_dir = os.path.join(CFG["out"]["app_dir"], CFG["out"]["audio_dir"])
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(aud_dir, exist_ok=True)

    print("1) 抓取 RSS")
    pool = []
    for feed in CFG["feeds"]:
        try:
            raw = fetch(feed["url"])
            got = parse_feed(raw, feed)
            print(f"   {feed['name']:<20} {len(got)} 条")
            pool += got
        except Exception as e:
            print(f"   {feed['name']:<20} FAIL {str(e)[:60]}")

    # 去重
    seen, uniq = set(), []
    for it in pool:
        k = it["title"].lower()[:80]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)

    # 相关性打分：只留真正对口的金融/AI/科技/政策新闻
    KEY = {
        "finance": ["market", "stock", "bond", "yield", "rate", "inflation", "earnings",
                    "revenue", "ipo", "investor", "bank", "dollar", "oil", "price",
                    "economy", "gdp", "tariff", "trade", "fund", "merger"],
        "ai": ["ai ", "artificial intelligence", "model", "llm", "openai", "anthropic",
               "neural", "training", "inference", "agent", "dataset", "gpu", "chip",
               "machine learning", "transformer"],
        "tech": ["chip", "semiconductor", "cloud", "security", "privacy", "startup",
                 "software", "app", "platform", "hardware", "robot", "quantum",
                 "battery", "satellite", "data center", "android", "ios"],
        "policy": ["regulat", "law", "antitrust", "policy", "government", "court",
                   "ban ", "rule", "bill", "senate", "congress", "ministry", "eu ",
                   "sanction", "compliance", "privacy act", "standard"],
    }
    def score(it):
        blob = (it["title"] + " " + it["summary"]).lower()
        s = sum(1 for k in KEY.get(it["category"], []) if k in blob)
        if any(x in blob for x in ["houthi", "missile", "election", "celebrity", "sports", "kardashian"]):
            s -= 3
        return s

    scored = sorted(uniq, key=score, reverse=True)
    print(f"2) 选稿（去重后 {len(uniq)} 条，目标 {args.limit}，按相关性排序）")
    picked, per_cat = [], {}
    for it in scored:
        if score(it) < 1:
            continue
        c = it["category"]
        if per_cat.get(c, 0) >= 2:
            continue
        picked.append(it)
        per_cat[c] = per_cat.get(c, 0) + 1
        if len(picked) >= args.limit:
            break
    for it in picked:
        print(f"   [{it['category']:<8} score={score(it):>2}] {it['title'][:62]}")

    print("3) 本地模型做摘要/翻译/生词")
    items = []
    for i, it in enumerate(picked, 1):
        try:
            data = summarize(it, CFG["llm"])
            items.append(data)
            print(f"   [{i}/{len(picked)}] {data.get('title_en','')[:58]}")
        except Exception as e:
            print(f"   [{i}/{len(picked)}] FAIL {str(e)[:80]}")

    today = dt.date.today().isoformat()
    payload = {"date": today,
               "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "items": items}
    path = os.path.join(out_dir, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, today + ".json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"4) 写入 {path}（{len(items)} 条）")

    audio_index = {"generated_at": payload["generated_at"], "items": []}
    if not args.no_tts and items:
        mp3 = os.path.join(aud_dir, today + "-briefing.mp3")
        try:
            script = make_audio(items, mp3, CFG["tts"])
            size = os.path.getsize(mp3) / 1024
            audio_index["items"].append({
                "title": "Daily Briefing", "date": today,
                "file": "data/audio/" + os.path.basename(mp3),
                "script": script, "duration": f"{size:.0f} KB"})
            print(f"5) 音频 {mp3}（{size:.0f} KB）")
        except Exception as e:
            print(f"5) 音频失败: {e}")
    with open(os.path.join(aud_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(audio_index, f, ensure_ascii=False, indent=2)
    print("完成")


if __name__ == "__main__":
    main()
