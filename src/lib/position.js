// Shared valuation-position helpers.
//
// Single source of truth for "where is the current price within the cheap↔expensive
// band". Previously this logic was duplicated (with slightly different thresholds)
// across WatchlistView, BandChart and summarize.js.

// Prefer the PE method when available (better for growth stocks whose yield method
// badly underestimates fair value); otherwise fall back to the yield method.
export function preferredBands(d) {
  if (d?.valuation_pe) return { bands: d.valuation_pe, method: 'pe' }
  if (d?.valuation_yield) return { bands: d.valuation_yield, method: 'yield' }
  return null
}

// 0% = sitting at the cheap price, 100% = at the expensive price. Can go <0 / >100
// when price is outside the historical band. Returns null when undefined.
export function positionPct(price, bands) {
  if (!price || !bands) return null
  if (bands.expensive === bands.cheap) return null
  return Math.round(((price - bands.cheap) / (bands.expensive - bands.cheap)) * 100)
}

// Position → { label, text (Tailwind text colour), bar (Tailwind bg colour) }.
// One threshold scheme reused everywhere, matching the README's four tiers.
export function positionTier(pct) {
  if (pct == null) return { label: '—', text: 'text-slate-400', bar: 'bg-slate-300' }
  if (pct <= 25) return { label: '便宜', text: 'text-emerald-600', bar: 'bg-emerald-500' }
  if (pct <= 50) return { label: '合理偏便宜', text: 'text-emerald-500', bar: 'bg-emerald-400' }
  if (pct <= 75) return { label: '合理偏貴', text: 'text-amber-600', bar: 'bg-amber-500' }
  if (pct <= 100) return { label: '昂貴', text: 'text-red-500', bar: 'bg-red-500' }
  return { label: '超昂貴', text: 'text-red-600', bar: 'bg-red-600' }
}

// Clamp position to [0,100] for rendering a bar marker.
export function clampPct(pct) {
  if (pct == null) return null
  return Math.max(0, Math.min(100, pct))
}
