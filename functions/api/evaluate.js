/**
 * POST /api/evaluate
 * 输入：multipart/form-data，字段 audio（录音 blob）、可选 topic、duration
 * 输出：{ ok, transcript, words, wpm, fillers, long_pauses, feedback[], score }
 *
 * 打分思路（不装模型也能给合理反馈）：
 *  1) Whisper 转写，拿到逐词时间戳
 *  2) 语速 = 词数 / 时长；停顿 = 相邻词间隔 > 0.6s 的次数
 *  3) 填充词（uh/um/like/you know）计数
 *  4) 给三个维度分数：流利度、用词丰富度、结构
 */
const FILLERS = ['uh', 'um', 'erm', 'hmm', 'like', 'you know', 'i mean', 'sort of', 'kind of'];

export async function onRequestPost({ request, env }) {
  try {
    const form = await request.formData();
    const file = form.get('audio');
    const duration = Number(form.get('duration') || 0);
    if (!file) return json({ ok: false, error: 'missing audio' }, 400);

    const buf = await file.arrayBuffer();
    if (buf.byteLength > 12 * 1024 * 1024) return json({ ok: false, error: 'audio too large (>12MB)' }, 413);

    const audio = [...new Uint8Array(buf)];
    const stt = await env.AI.run('@cf/openai/whisper', { audio });
    const transcript = (stt.text || '').trim();
    const words = stt.words || [];

    const wc = transcript.split(/\s+/).filter(Boolean).length;
    const dur = duration > 0 ? duration : estimateDuration(words);
    const wpm = dur > 0 ? Math.round((wc / dur) * 60) : 0;

    let longPauses = 0;
    for (let i = 1; i < words.length; i++) {
      const gap = (words[i].start ?? 0) - (words[i - 1].end ?? 0);
      if (gap > 0.6) longPauses++;
    }

    const lower = ' ' + transcript.toLowerCase() + ' ';
    const fillers = FILLERS.reduce((n, f) => n + (lower.split(' ' + f + ' ').length - 1), 0);
    const uniq = new Set(transcript.toLowerCase().match(/[a-z']{3,}/g) || []).size;
    const ttr = wc > 0 ? uniq / wc : 0;

    const scores = {
      fluency: clamp(100 - Math.abs(wpm - 130) * 0.8 - longPauses * 3 - fillers * 2),
      vocabulary: clamp(40 + ttr * 120),
      length: clamp(wc >= 90 ? 100 : (wc / 90) * 100)
    };
    const score = Math.round((scores.fluency * 0.5 + scores.vocabulary * 0.25 + scores.length * 0.25));

    const feedback = [];
    if (wpm < 100) feedback.push(`语速偏慢（${wpm} wpm），托福口语舒适区约 120–150 wpm。`);
    else if (wpm > 165) feedback.push(`语速偏快（${wpm} wpm），注意留出让听者消化的停顿。`);
    else feedback.push(`语速合适（${wpm} wpm）。`);
    if (longPauses > 4) feedback.push(`超过 0.6 秒的停顿 ${longPauses} 次，试着用 well / actually 之类的过渡词填空。`);
    if (fillers > 3) feedback.push(`填充词 ${fillers} 个（um / like 等），减少它们会显得更自信。`);
    if (ttr < 0.45 && wc > 40) feedback.push(`用词重复较多（独特词占比 ${(ttr * 100).toFixed(0)}%），可以换同义表达。`);
    if (wc < 60) feedback.push(`只说了 ${wc} 词，托福独立口语建议 90–120 词。`);

    return json({
      ok: true, transcript, word_count: wc, duration: round(dur, 2), wpm,
      long_pauses: longPauses, fillers, unique_ratio: round(ttr, 3),
      scores, score, feedback
    });
  } catch (e) {
    return json({ ok: false, error: String(e && e.message || e) }, 500);
  }
}

function estimateDuration(words) {
  if (!words || !words.length) return 0;
  return (words[words.length - 1].end ?? 0) - (words[0].start ?? 0);
}
function clamp(v) { return Math.max(0, Math.min(100, v)); }
function round(v, n) { const p = Math.pow(10, n); return Math.round(v * p) / p; }
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' }
  });
}
