// Browser-side FinMind client + on-demand stock fetch.
// Used as a fallback in StockDetailView when no static data/tw/{code}.json exists,
// so users can look up any TW stock without the repo owner pre-loading it.

import {
  parseYear,
  pickLatestDividend,
  computeYieldValuation,
  computePeValuation,
} from './valuation.js'

const FINMIND_BASE = 'https://api.finmindtrade.com/api/v4/data'
const CACHE_PREFIX = 'triprice.dynamic.v2.' // bumped after switching to 5/95 percentile method
const CACHE_TTL_MS = 6 * 60 * 60 * 1000 // 6 hours

async function finmind(dataset, params) {
  const url = new URL(FINMIND_BASE)
  url.searchParams.set('dataset', dataset)
  for (const [k, v] of Object.entries(params)) {
    url.searchParams.set(k, v)
  }
  const res = await fetch(url)
  if (!res.ok) throw new Error(`FinMind ${dataset}: HTTP ${res.status}`)
  const j = await res.json()
  if (j.status !== 200) throw new Error(`FinMind ${dataset}: ${j.msg || 'error'}`)
  return j.data || []
}

function ymd(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function round(n, d) {
  return Number(Number(n).toFixed(d))
}

function getCached(code) {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + code)
    if (!raw) return null
    const { data, fetched_at } = JSON.parse(raw)
    if (Date.now() - fetched_at > CACHE_TTL_MS) {
      localStorage.removeItem(CACHE_PREFIX + code)
      return null
    }
    return data
  } catch {
    return null
  }
}

function setCached(code, data) {
  try {
    localStorage.setItem(
      CACHE_PREFIX + code,
      JSON.stringify({ data, fetched_at: Date.now() }),
    )
  } catch {
    // localStorage full or disabled — ignore
  }
}

export async function fetchStockDynamic(code, { useCache = true } = {}) {
  if (useCache) {
    const cached = getCached(code)
    if (cached) return cached
  }

  const today = new Date()
  const todayStr = ymd(today)
  const threeY = ymd(new Date(today.getTime() - 365 * 3.05 * 86400 * 1000))
  const fiveY = ymd(new Date(today.getTime() - 365 * 5.2 * 86400 * 1000))

  // 1. Daily prices for past 3 years
  const prices = await finmind('TaiwanStockPrice', {
    data_id: code,
    start_date: threeY,
    end_date: todayStr,
  })
  if (prices.length === 0) {
    throw new Error('找不到此股票，請確認代號正確')
  }
  const latest = prices[prices.length - 1]
  const prev = prices[prices.length - 2]
  const currentPrice = parseFloat(latest.close)
  const change = prev ? round(currentPrice - parseFloat(prev.close), 2) : 0
  const changePct = prev ? round((change / parseFloat(prev.close)) * 100, 2) : 0

  // 2. Dividend history (5 years)
  let divData = []
  try {
    divData = await finmind('TaiwanStockDividend', {
      data_id: code,
      start_date: fiveY,
      end_date: todayStr,
    })
  } catch {
    // Some codes have no dividend data
  }
  const byYear = {}
  for (const d of divData) {
    const year = parseYear(d.year)
    if (year == null) continue
    const cash =
      (parseFloat(d.CashEarningsDistribution) || 0) +
      (parseFloat(d.CashStatutorySurplus) || 0)
    byYear[year] = (byYear[year] || 0) + cash
  }
  const [latestYear, latestDividend] = pickLatestDividend(byYear, today.getFullYear())

  // 3. Aggregate prices by year
  const yearCloses = {}
  for (const p of prices) {
    const year = parseInt(p.date.slice(0, 4), 10)
    const close = parseFloat(p.close)
    if (close > 0) {
      if (!yearCloses[year]) yearCloses[year] = []
      yearCloses[year].push(close)
    }
  }

  // 4. PER history (skip silently if 404 — ETFs)
  const yearPes = {}
  try {
    const perData = await finmind('TaiwanStockPER', {
      data_id: code,
      start_date: threeY,
      end_date: todayStr,
    })
    for (const d of perData) {
      const year = parseInt(d.date.slice(0, 4), 10)
      const pe = parseFloat(d.PER) || 0
      if (pe > 0) {
        if (!yearPes[year]) yearPes[year] = []
        yearPes[year].push(pe)
      }
    }
  } catch {
    // ETFs have no PER
  }

  // 5. Last 3 trailing years (include current if >=30 trading days)
  const allYears = Object.keys(yearCloses)
    .map(Number)
    .sort((a, b) => b - a)
  const candidateYears = []
  for (const y of allYears) {
    if (y === today.getFullYear() && yearCloses[y].length < 30) continue
    candidateYears.push(y)
    if (candidateYears.length >= 3) break
  }

  const allYields = []
  const allPes = []
  for (const year of candidateYears) {
    const closes = yearCloses[year] || []
    if (closes.length === 0) continue
    let div = byYear[year] || 0
    if (year === today.getFullYear()) {
      const prevDiv = byYear[year - 1] || 0
      if (prevDiv > 0 && (div === 0 || div < 0.5 * prevDiv)) div = prevDiv
    }
    if (div > 0) {
      for (const c of closes) {
        if (c > 0) allYields.push(div / c)
      }
    }
    const pes = yearPes[year] || []
    allPes.push(...pes)
  }

  // 6. Quarterly EPS (4 quarters for TTM + display)
  const epsQuarterly = []
  let epsTtm = null
  try {
    const fsData = await finmind('TaiwanStockFinancialStatements', {
      data_id: code,
      start_date: ymd(new Date(today.getTime() - 750 * 86400 * 1000)),
      end_date: todayStr,
    })
    const epsRows = fsData.filter((r) => r.type === 'EPS')
    epsRows.sort((a, b) => b.date.localeCompare(a.date))
    for (const r of epsRows.slice(0, 8)) {
      epsQuarterly.push({ period: r.date, eps: round(parseFloat(r.value), 2) })
    }
    if (epsQuarterly.length >= 4) {
      epsTtm = round(
        epsQuarterly.slice(0, 4).reduce((s, q) => s + q.eps, 0),
        2,
      )
    }
    const periodMap = Object.fromEntries(epsQuarterly.map((q) => [q.period, q.eps]))
    for (const q of epsQuarterly) {
      const d = new Date(q.period)
      d.setFullYear(d.getFullYear() - 1)
      const prevPeriod = ymd(d)
      const prevEps = periodMap[prevPeriod]
      if (prevEps != null && prevEps !== 0) {
        q.yoy = round((q.eps - prevEps) / Math.abs(prevEps), 4)
      } else {
        q.yoy = null
      }
    }
  } catch {
    // skip if no statements
  }

  // 7. Compute valuations
  const [valuationYield, yieldStats] = computeYieldValuation(latestDividend, allYields)
  const [valuationPe, peStats] = computePeValuation(epsTtm, allPes)

  // 8. Per-year dividend history
  const dividendHistory = []
  const sortedDivYears = Object.keys(byYear)
    .map(Number)
    .sort((a, b) => b - a)
    .slice(0, 5)
  for (const year of sortedDivYears) {
    const dividend = byYear[year]
    const closes = yearCloses[year] || []
    let yieldVal = null
    if (closes.length > 0 && dividend > 0) {
      const avgClose = closes.reduce((a, b) => a + b, 0) / closes.length
      yieldVal = round(dividend / avgClose, 4)
    }
    dividendHistory.push({
      year,
      cash_dividend: round(dividend, 4),
      yield: yieldVal,
    })
  }

  const result = {
    code,
    name: code,
    updated:
      new Date().toISOString().replace('T', ' ').slice(0, 19) + '+08:00',
    close_date: latest.date,
    current_price: currentPrice,
    change,
    change_pct: changePct,
    dividend_used: round(latestDividend, 4),
    dividend_year: latestYear,
    eps_ttm: epsTtm,
    valuation_yield: valuationYield,
    yield_stats: yieldStats,
    valuation_pe: valuationPe,
    pe_stats: peStats,
    eps_quarterly: epsQuarterly.slice(0, 4),
    dividend_history: dividendHistory,
    _dynamic: true,
  }

  setCached(code, result)
  return result
}
