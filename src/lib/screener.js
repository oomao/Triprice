// Browser-side computation utilities for the multi-condition screener.
//
// All inputs come from the static JSON the fetch scripts produce:
//   tw/{code}.json         current_price / yield_stats / pe_stats / valuation_*
//                          eps_ttm / pbr / kline (1Y daily OHLC)
//   data/fx.json           vix
//
// We avoid mutating the source data — these are pure functions returning
// numbers/booleans the screener UI uses to evaluate each condition.

// ── Indicators ───────────────────────────────────────────────────────────────

/** Simple moving average over the last `period` closes. Returns null if too few. */
export function ma(kline, period = 60) {
  if (!kline || kline.length < period) return null
  const slice = kline.slice(-period)
  return slice.reduce((s, k) => s + (k.c || 0), 0) / period
}

/** Aggregate daily kline rows into monthly OHLC.
 *  Each month = the last trading day's close + that month's high/low/open. */
export function monthlyOHLC(kline) {
  if (!kline?.length) return []
  const buckets = new Map()
  for (const k of kline) {
    const ym = k.d?.slice(0, 7)
    if (!ym) continue
    if (!buckets.has(ym)) {
      buckets.set(ym, { d: ym, o: k.o, h: k.h, l: k.l, c: k.c })
    } else {
      const b = buckets.get(ym)
      if (k.h > b.h) b.h = k.h
      if (k.l < b.l) b.l = k.l
      b.c = k.c // overwrite — latest close in the month wins
    }
  }
  return Array.from(buckets.values())
}

/** KD stochastic on monthly bars. Period = 9 by default (台股慣例).
 *  Returns array of {d, k, d_val} matching monthly bars (first period-1 are null). */
export function monthlyKD(kline, period = 9) {
  const months = monthlyOHLC(kline)
  if (months.length < period) return []
  const rsv = []
  for (let i = 0; i < months.length; i++) {
    if (i < period - 1) { rsv.push(null); continue }
    let hi = -Infinity, lo = Infinity
    for (let j = i - period + 1; j <= i; j++) {
      if (months[j].h > hi) hi = months[j].h
      if (months[j].l < lo) lo = months[j].l
    }
    const c = months[i].c
    rsv.push(hi === lo ? 50 : ((c - lo) / (hi - lo)) * 100)
  }
  // K = prev_K * 2/3 + RSV * 1/3, seeded at 50
  // D = prev_D * 2/3 + K * 1/3, seeded at 50
  const out = []
  let k = 50, d = 50
  for (let i = 0; i < months.length; i++) {
    const r = rsv[i]
    if (r == null) { out.push({ d: months[i].d, k: null, d_val: null }); continue }
    k = (k * 2) / 3 + r / 3
    d = (d * 2) / 3 + k / 3
    out.push({ d: months[i].d, k, d_val: d })
  }
  return out
}

/** Cash dividend yield based on the dividend used by the valuation script. */
export function yieldPct(stock) {
  if (!stock?.dividend_used || !stock.current_price) return null
  return (stock.dividend_used / stock.current_price) * 100
}

/** Where does today's PE sit within the 3-year [low..high] band?
 *  0% = low percentile bound, 100% = high percentile bound. */
export function pePercentile(stock) {
  const eps = stock?.eps_ttm
  const stats = stock?.pe_stats
  if (!eps || eps <= 0 || !stats) return null
  const currentPE = stock.current_price / eps
  const { low, high } = stats
  if (low == null || high == null || high === low) return null
  return ((currentPE - low) / (high - low)) * 100
}

// ── Conditions ───────────────────────────────────────────────────────────────
//
// Each condition is a function (stock, params, marketCtx) -> bool | null.
// Returns null when the input data isn't available (cannot judge).

export const CONDITIONS = {
  vix_high: {
    label: 'VIX 大盤恐慌',
    hint: 'VIX ≥ 設定值（市場大幅恐慌時，極端便宜可能浮現）',
    defaultParam: 30,
    paramUnit: '',
    isMarketWide: true,
    eval(_stock, threshold, ctx) {
      if (ctx?.vix == null) return null
      return ctx.vix >= threshold
    },
  },
  monthly_kd_low: {
    label: '月 KD 低檔',
    hint: '月 K 值 ≤ 設定值（中長期超賣）',
    defaultParam: 30,
    paramUnit: '',
    eval(stock, threshold) {
      const kd = monthlyKD(stock.kline)
      const last = kd[kd.length - 1]
      if (!last || last.k == null) return null
      return last.k <= threshold
    },
  },
  pb_low: {
    label: '股價淨值比偏低',
    hint: 'PBR ≤ 設定值（小於 1 通常視為破底）',
    defaultParam: 1.5,
    paramUnit: '',
    eval(stock, threshold) {
      if (stock.pbr == null) return null
      return stock.pbr <= threshold
    },
  },
  yield_high: {
    label: '現金殖利率高',
    hint: '殖利率 ≥ 設定值（高息穩配族群）',
    defaultParam: 5,
    paramUnit: '%',
    eval(stock, threshold) {
      const y = yieldPct(stock)
      if (y == null) return null
      return y >= threshold
    },
  },
  pe_low_pctile: {
    label: 'PE 落歷史低位',
    hint: '當前 PE 落在近 3 年區間第 N 百分位以下',
    defaultParam: 30,
    paramUnit: '%',
    eval(stock, threshold) {
      const p = pePercentile(stock)
      if (p == null) return null
      return p <= threshold
    },
  },
  below_ma60: {
    label: '跌破 60 日均線',
    hint: '收盤 < 60 日 MA（中期破壞訊號 / 落底機會）',
    defaultParam: 0,        // unused, kept for shape consistency
    paramUnit: '',
    paramless: true,
    eval(stock) {
      const m = ma(stock.kline, 60)
      if (m == null || stock.current_price == null) return null
      return stock.current_price < m
    },
  },
}

// ── Helpers for the view ─────────────────────────────────────────────────────

/** Build a per-stock evaluation: which conditions hit, plus raw values. */
export function evaluate(stock, activeConditions, params, marketCtx) {
  const hits = {}
  let hitCount = 0
  for (const key of activeConditions) {
    const c = CONDITIONS[key]
    if (!c) continue
    const r = c.eval(stock, params[key], marketCtx)
    hits[key] = r
    if (r === true) hitCount += 1
  }
  return {
    code: stock.code,
    name: stock.name,
    current_price: stock.current_price,
    yield_pct: yieldPct(stock),
    pbr: stock.pbr,
    pe_pctile: pePercentile(stock),
    monthly_k: (() => {
      const kd = monthlyKD(stock.kline)
      return kd[kd.length - 1]?.k ?? null
    })(),
    ma60: ma(stock.kline, 60),
    hits,
    hitCount,
  }
}
