// Estimation logic mirroring scripts/fetch_tw.py — used by browser-side dynamic fetch.

export function parseYear(y) {
  if (y == null) return null
  const s = String(y).trim()
  const m = /^(\d+)/.exec(s)
  if (!m) return null
  let n = parseInt(m[1], 10)
  if (n < 200) n += 1911
  return n
}

export function pickLatestDividend(byYear, currentYear) {
  const sortedYears = Object.keys(byYear)
    .map(Number)
    .sort((a, b) => b - a)
  if (sortedYears.length === 0) return [null, 0]
  const top = sortedYears[0]
  const topDiv = byYear[top]
  if (top === currentYear && sortedYears.length >= 2) {
    const prev = sortedYears[1]
    const prevDiv = byYear[prev]
    if (prevDiv > 0 && topDiv < 0.5 * prevDiv) {
      return [prev, prevDiv]
    }
  }
  return [top, topDiv]
}

const HIGH_PCT = 0.95 // trim top 5%
const LOW_PCT = 0.05  // trim bottom 5%

function percentile(sortedData, p) {
  if (!sortedData.length) return null
  const n = sortedData.length
  if (n === 1) return sortedData[0]
  const k = (n - 1) * p
  const f = Math.floor(k)
  const c = k - f
  if (f + 1 >= n) return sortedData[n - 1]
  return sortedData[f] * (1 - c) + sortedData[f + 1] * c
}

export function computeYieldValuation(latestDividend, yields) {
  const pos = yields.filter((y) => y > 0).sort((a, b) => a - b)
  if (pos.length === 0 || !latestDividend) return [null, null]
  const high = percentile(pos, HIGH_PCT)
  const low = percentile(pos, LOW_PCT)
  const avg = pos.reduce((a, b) => a + b, 0) / pos.length
  return [
    {
      cheap: round(latestDividend / high, 2),
      fair: round(latestDividend / avg, 2),
      expensive: round(latestDividend / low, 2),
    },
    { high: round(high, 4), avg: round(avg, 4), low: round(low, 4) },
  ]
}

export function computePeValuation(epsTtm, pes) {
  const pos = pes.filter((p) => p > 0).sort((a, b) => a - b)
  if (pos.length === 0 || !epsTtm || epsTtm <= 0) return [null, null]
  const high = percentile(pos, HIGH_PCT)
  const low = percentile(pos, LOW_PCT)
  const avg = pos.reduce((a, b) => a + b, 0) / pos.length
  return [
    {
      cheap: round(epsTtm * low, 2),
      fair: round(epsTtm * avg, 2),
      expensive: round(epsTtm * high, 2),
    },
    { high: round(high, 2), avg: round(avg, 2), low: round(low, 2) },
  ]
}

function round(n, d) {
  return Number(Number(n).toFixed(d))
}
