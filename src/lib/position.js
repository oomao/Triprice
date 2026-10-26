// Shared valuation-position helpers.
//
// Single source of truth for "where is the current price within the cheap↔expensive
// band". This logic used to be copied into WatchlistView, BandChart, summarize.js and
// StockDetailView with different thresholds — the list could say 合理偏便宜 41% while
// the stock page said 合理偏貴 for the same method, because `fair` is the 3-year
// median, not the midpoint of cheap and expensive.
//
// Position is therefore piecewise: 0% = cheap price, 50% = fair price,
// 100% = expensive price, so the percentage and the tier label always agree.

// Prefer the PE method when available (better for growth stocks whose yield method
// badly underestimates fair value); otherwise fall back to the yield method.
export function preferredBands(d) {
  if (d?.valuation_pe) return { bands: d.valuation_pe, method: 'pe' }
  if (d?.valuation_yield) return { bands: d.valuation_yield, method: 'yield' }
  return null
}

export const METHOD_LABEL = { pe: 'PE 法', yield: '殖利率法' }

// <0 below cheap, >100 above expensive. null when undefined.
export function positionPct(price, bands) {
  if (!price || !bands) return null
  const { cheap, fair, expensive } = bands
  if (cheap == null || expensive == null || !(expensive > cheap)) return null
  const mid = fair > cheap && fair < expensive ? fair : (cheap + expensive) / 2
  const pct = price <= mid
    ? ((price - cheap) / (mid - cheap)) * 50
    : 50 + ((price - mid) / (expensive - mid)) * 50
  return Math.round(pct)
}

// Position → { key, label, short, text (Tailwind text colour), bar (bg colour), chip }.
// Tier boundaries are the three prices themselves (README's four tiers).
const TIERS = {
  none:      { key: 'none',      label: '—',          short: '—',  text: 'text-slate-400',   bar: 'bg-slate-300',   chip: 'bg-slate-100 text-slate-500 border-slate-200' },
  cheap:     { key: 'cheap',     label: '便宜',       short: '便宜', text: 'text-emerald-600', bar: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  fairLow:   { key: 'fairLow',   label: '合理偏便宜', short: '偏便宜', text: 'text-emerald-500', bar: 'bg-emerald-400', chip: 'bg-emerald-50/60 text-emerald-600 border-emerald-100' },
  fairHigh:  { key: 'fairHigh',  label: '合理偏貴',   short: '偏貴', text: 'text-amber-600',   bar: 'bg-amber-500',   chip: 'bg-amber-50 text-amber-700 border-amber-200' },
  expensive: { key: 'expensive', label: '昂貴',       short: '昂貴', text: 'text-red-500',     bar: 'bg-red-500',     chip: 'bg-red-50 text-red-600 border-red-200' },
}
export const TIER_ORDER = ['cheap', 'fairLow', 'fairHigh', 'expensive']
export const tierByKey = (k) => TIERS[k] || TIERS.none

export function positionTier(pct) {
  if (pct == null) return TIERS.none
  if (pct <= 0) return TIERS.cheap
  if (pct <= 50) return TIERS.fairLow
  if (pct <= 100) return TIERS.fairHigh
  return TIERS.expensive
}

// Clamp position to [0,100] for rendering a bar marker.
export function clampPct(pct) {
  if (pct == null) return null
  return Math.max(0, Math.min(100, pct))
}

// % move needed from price to reach target (e.g. -12.3 = must fall 12.3%).
export function distancePct(price, target) {
  if (!price || !target) return null
  return Math.round(((target - price) / price) * 1000) / 10
}

// Everything the list / stock page shows about one stock's valuation, per method.
export function valuationView(d) {
  const price = d?.current_price
  const one = (bands, method) => {
    if (!bands) return null
    const pct = positionPct(price, bands)
    return {
      method,
      bands,
      pct,
      bar: clampPct(pct),
      tier: positionTier(pct),
      toFair: distancePct(price, bands.fair),
      toCheap: distancePct(price, bands.cheap),
    }
  }
  const pe = one(d?.valuation_pe, 'pe')
  const yld = one(d?.valuation_yield, 'yield')
  const primary = pe || yld
  const secondary = primary === pe ? yld : null
  // The two methods "disagree" when their positions are half a band or more apart
  // (e.g. PE 4% vs yield 97%) — a tier-distance rule missed such neighbours.
  let divergent = false
  if (pe && yld && pe.pct != null && yld.pct != null) {
    divergent = Math.abs(pe.pct - yld.pct) >= 50
  }
  const curYield = d?.dividend_used && price ? Math.round((d.dividend_used / price) * 10000) / 100 : null
  const curPe = d?.eps_ttm > 0 && price ? Math.round((price / d.eps_ttm) * 10) / 10 : null
  return { price, pe, yld, primary, secondary, divergent, curYield, curPe }
}
