# TOEFL 每日 · 部署说明

一个 PWA：单词（番茄 + 间隔重复）、每日新闻精读、听力跟读、口语录音评测。
纯静态前端 + Cloudflare Pages Functions（口语评测）+ 本地 Python 管线（每天生成内容）。

```
toefl-app/
  index.html            # 前端（单文件）
  manifest.webmanifest  # PWA
  sw.js                 # 离线缓存
  data/news/index.json  # 每天由管线生成
  data/audio/index.json # 每天由管线生成 + *.mp3
  functions/api/evaluate.js  # 口语评测（Workers AI Whisper）
  pipeline/             # 每日管线（本地跑）
  wrangler.toml
```

## 一、手机先试（现在就能用）

1. 电脑上跑静态服务：
   ```
   cd E:\2026\toefl-app
   python -m http.server 8899
   ```
2. 手机连同一个 Wi-Fi，浏览器打开 `http://<电脑内网IP>:8899`
3. Chrome 菜单 → **添加到主屏幕**（安卓），就是一个全屏 App

## 二、每天生成内容（本地，不花钱）

```powershell
cd E:\2026\toefl-app\pipeline
python run_daily.py            # 抓取 → 摘要/翻译/生词 → 音频 → data/
```
- 默认用本机 **Ollama**（qwen3:14b）；连不上会退到 Strata 引擎（8080）
- 抓 7 个源：CNBC / BBC Business / Fed / TechCrunch / Ars Technica / MIT Tech Review / arXiv cs.AI
- 每天约 5 条，按“金融/AI/科技/政策”相关性打分挑选，每类最多 2 条
- 音频是一段 40–90 秒的英文简报（edge-tts，`en-US-AriaNeural`）

### 每天自动跑（Windows 任务计划）

管理员 PowerShell 执行一次：
```powershell
schtasks /Create /TN "TOEFL每日" /SC DAILY /ST 07:00 /RL HIGHEST ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File E:\2026\toefl-app\pipeline\run-daily.ps1"
```
`run-daily.ps1` 会：跑管线 → `git add/commit/push` → Cloudflare 自动重新部署。

## 三、部署到 Cloudflare Pages

### 方式 A：命令行（最快）

```powershell
cd E:\2026\toefl-app
npx wrangler login          # 浏览器授权一次
npx wrangler pages deploy . --project-name toefl-daily
```
第一次会让你创建项目；完成后拿到 `https://toefl-daily.pages.dev`。

> 注意：`--project-name` 里的点号会被改成连字符；部署目录是 `.`（含 functions/ 会被识别为 Pages Functions）。

### 方式 B：接 GitHub（以后改代码自动部署）

1. 建一个空仓库，把 `E:\2026\toefl-app` 推上去
2. Cloudflare 控制台 → Workers & Pages → Create → Pages → Connect to Git
3. Build command 留空，Build output directory 填 `/`
4. 部署完打开 `https://<项目名>.pages.dev`

### 开启口语评测（必须）

Pages 项目 → Settings → Functions → **Workers AI binding**：
- Variable name: `AI`

（免费额度每天 10,000 Neurons，个人练习够用；Whisper 每次几十到几百 Neurons。）

## 四、口语评测怎么打分

`functions/api/evaluate.js`：
1. 录音上传（≤12 MB）
2. Workers AI `@cf/openai/whisper` 转写，拿逐词时间戳
3. 计算：语速 wpm、>0.6 秒停顿次数、填充词计数、独特词占比
4. 三项评分：流利度（50%）、用词（25%）、长度（25%）→ 总分 + 具体建议

**已知限制**：这是“流利度 + 内容”评测，不是逐音素的发音打分。要做真正的发音评分，需要加一个音素级模型（wav2vec2 + 强制对齐），那是第二阶段的事。

## 五、版权与合规

- 新闻只做**摘要 + 要点 + 链接回原站**，不转载全文
- 音频是模型朗读的摘要，不是原文录音
- 生词与翻译由本地模型生成，可能有个别错误，每天会抽检
