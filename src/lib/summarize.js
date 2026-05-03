// Browser-side per-stock summary generator.
// Calls the user's chosen LLM provider directly with their own API key.
// Result cached in localStorage keyed by code + fingerprint so flipping back to
// the page doesn't trigger another paid call.

const SYSTEM_PROMPT =
  '你是台股資料整理助理。你的任務是把使用者提供的客觀資料壓縮成 2-3 句的繁體中文摘要。\n\n' +
  '嚴格規則：\n' +
  '1. 只能根據使用者提供的資料寫，不能編造、不能引用未提供的數字\n' +
  '2. 不能給投資建議、不能用「建議買進/賣出/持有」等字眼\n' +
  '3. 不能用情緒誇張用語（暴漲、噴出、神級、絕佳⋯）\n' +
  '4. 用平實敘述，類似一段事實摘要\n' +
  '5. 整段不超過 120 字\n' +
  '6. 結構：第一句點出公司類型/估值狀態（用 PE 法為主），第二句點出 1 個值得注意的觀察，可選第三句補充風險提示\n' +
  '7. 不要寫前言、不要寫結語，直接出摘要本文'

const PROMPT_VERSION = 'v1'
const CACHE_PREFIX = 'triprice.summary.v1.'

function positionPct(price, bands) {
  if (!price || !bands) return null
  const { cheap, expensive } = bands
  if (cheap == null || expensive == null || cheap === expensive) return null
  return Math.round(((price - cheap) / (expensive - cheap)) * 100)
}

export function buildPrompt(d) {
  const parts = []
  parts.push(`代號 ${d.code} ${d.name || ''}`)
  parts.push(`現價 ${d.current_price} 元`)
  if (d.change_pct != null) parts.push(`今日漲跌 ${d.change_pct >= 0 ? '+' : ''}${d.change_pct.toFixed(2)}%`)
  if (d.eps_ttm != null) parts.push(`近 4 季 EPS 合計 ${d.eps_ttm}`)
  if (d.dividend_used) parts.push(`最新年度現金股利 ${d.dividend_used}`)
  if (d.valuation_yield) {
    const pos = positionPct(d.current_price, d.valuation_yield)
    let line = `殖利率法估值 便宜 ${d.valuation_yield.cheap} / 合理 ${d.valuation_yield.fair} / 昂貴 ${d.valuation_yield.expensive}`
    if (pos != null) line += `（目前位置 ${pos}%）`
    parts.push(line)
  }
  if (d.valuation_pe) {
    const pos = positionPct(d.current_price, d.valuation_pe)
    let line = `PE 法估值 便宜 ${d.valuation_pe.cheap} / 合理 ${d.valuation_pe.fair} / 昂貴 ${d.valuation_pe.expensive}`
    if (pos != null) line += `（目前位置 ${pos}%）`
    parts.push(line)
  }
  if (d.eps_quarterly?.[0]?.yoy != null) {
    parts.push(`最新季度 EPS YoY ${d.eps_quarterly[0].yoy >= 0 ? '+' : ''}${(d.eps_quarterly[0].yoy * 100).toFixed(1)}%`)
  }
  if (d.adr?.premium_pct != null) {
    parts.push(`ADR 溢價 ${d.adr.premium_pct >= 0 ? '+' : ''}${d.adr.premium_pct.toFixed(2)}%`)
  }
  return parts.join(' | ')
}

async function digestHex(text) {
  const enc = new TextEncoder().encode(text)
  const buf = await crypto.subtle.digest('SHA-256', enc)
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 16)
}

export async function fingerprint(d, provider, model) {
  const payload = JSON.stringify({
    v: PROMPT_VERSION,
    provider,
    model,
    price: d.current_price,
    change_pct: d.change_pct,
    eps_ttm: d.eps_ttm,
    dividend_used: d.dividend_used,
    valuation_yield: d.valuation_yield,
    valuation_pe: d.valuation_pe,
    yield_stats_avg: d.yield_stats?.avg,
    pe_stats_avg: d.pe_stats?.avg,
    last_eps_yoy: d.eps_quarterly?.[0]?.yoy,
    adr_premium_pct: d.adr?.premium_pct,
  })
  return digestHex(payload)
}

// ── Provider HTTP clients ─────────────────────────────────────────────────────

async function callAnthropic(apiKey, model, system, user) {
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 400,
      system,
      messages: [{ role: 'user', content: user }],
    }),
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(`Anthropic ${r.status}: ${t.slice(0, 200)}`)
  }
  const j = await r.json()
  return (j.content || [])
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('')
    .trim()
}

async function callOpenAI(apiKey, model, system, user) {
  const r = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 400,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    }),
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(`OpenAI ${r.status}: ${t.slice(0, 200)}`)
  }
  const j = await r.json()
  return (j.choices?.[0]?.message?.content || '').trim()
}

async function callGoogle(apiKey, model, system, user) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: system }] },
      contents: [{ role: 'user', parts: [{ text: user }] }],
      generationConfig: { maxOutputTokens: 400, temperature: 0.3 },
    }),
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(`Google ${r.status}: ${t.slice(0, 200)}`)
  }
  const j = await r.json()
  const parts = j.candidates?.[0]?.content?.parts || []
  return parts.map((p) => p.text || '').join('').trim()
}

const CALLERS = {
  anthropic: callAnthropic,
  openai: callOpenAI,
  google: callGoogle,
}

export async function generateSummary({ data, provider, apiKey, model, force = false }) {
  if (!provider || !CALLERS[provider]) throw new Error(`未知供應商：${provider}`)
  if (!apiKey) throw new Error('請先到「設定」填入此供應商的 API key')
  const fp = await fingerprint(data, provider, model)
  const cacheKey = CACHE_PREFIX + data.code
  if (!force) {
    try {
      const raw = localStorage.getItem(cacheKey)
      if (raw) {
        const cached = JSON.parse(raw)
        if (cached.fingerprint === fp && cached.text) return cached
      }
    } catch {
      /* ignore cache parse errors */
    }
  }
  const text = await CALLERS[provider](apiKey, model, SYSTEM_PROMPT, buildPrompt(data))
  if (!text) throw new Error('LLM 回傳空字串')
  const result = {
    text,
    generated_at: new Date().toISOString().replace('T', ' ').slice(0, 19) + '+00:00',
    provider,
    model,
    fingerprint: fp,
  }
  try {
    localStorage.setItem(cacheKey, JSON.stringify(result))
  } catch {
    /* localStorage full */
  }
  return result
}

export function loadCachedSummary(code) {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + code)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function clearCachedSummary(code) {
  try {
    localStorage.removeItem(CACHE_PREFIX + code)
  } catch {
    /* ignore */
  }
}
