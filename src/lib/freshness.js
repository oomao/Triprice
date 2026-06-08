// Shared data-freshness helper.
//
// Single source of truth for the green/amber/red staleness badge. Previously this
// logic lived only inside ADRDashboardView, so the main decision surfaces (the
// stock list and the per-stock page) had no staleness signal at all — the site
// served month-old data with no warning when the cron silently failed.
//
// Thresholds are in hours and caller-supplied, because different surfaces have
// different cadences:
//   - ADR prediction (intraday-sensitive, updates after US close): 6h / 30h
//   - Valuation / list (updates each weekday ~14:00): use day-scale thresholds
//     (e.g. 80h / 168h) so a normal weekend gap does NOT trip a false alarm.

const GREEN = 'bg-emerald-50 border-emerald-300 text-emerald-700'
const AMBER = 'bg-amber-50 border-amber-300 text-amber-700'
const RED = 'bg-rose-50 border-rose-300 text-rose-700'

export function parseTpe(iso) {
  if (!iso) return null
  // Replace the space with "T" so strict engines (Safari) parse the timestamp.
  const t = Date.parse(String(iso).replace(' ', 'T'))
  return Number.isNaN(t) ? null : t
}

/**
 * @param {string} iso  Taipei timestamp, e.g. "2026-05-08 15:25:19+08:00" (or a bare date).
 * @param {object} opts {warnHours, staleHours, staleNote, now}
 * @returns {{ageHours:number, label:string, cls:string, stale:boolean}|null}
 */
export function computeFreshness(iso, opts = {}) {
  const {
    warnHours = 6,
    staleHours = 30,
    staleNote = 'cron 可能失敗',
    now = Date.now(),
  } = opts
  const ts = parseTpe(iso)
  if (ts == null) return null
  const ageHours = (now - ts) / 3.6e6
  let label
  if (ageHours <= 1) label = `${Math.max(0, Math.round(ageHours * 60))} 分鐘前更新`
  else if (ageHours < 48) label = `${ageHours.toFixed(1)} 小時前更新`
  else label = `${(ageHours / 24).toFixed(1)} 天前更新`

  let cls
  let stale = false
  if (ageHours <= warnHours) {
    cls = GREEN
  } else if (ageHours <= staleHours) {
    cls = AMBER
  } else {
    cls = RED
    stale = true
    label = `${(ageHours / 24).toFixed(1)} 天前 · ${staleNote}`
  }
  return { ageHours, label, cls, stale }
}
