// Shared data-freshness helper.
//
// Single source of truth for the green/amber/red staleness badge on the overview,
// the per-stock page and /adr.
//
// Raw age is a bad alarm: the ADR file written Saturday morning is still the newest
// possible one on Monday, yet a 30h threshold painted it red ("cron 可能失敗") every
// weekend — while a weekend-safe 7-day threshold let a dead TW cron go unnoticed for
// days. So with a `schedule`, lateness is measured against the NEXT EXPECTED update
// after the file's timestamp, not against "now".

const GREEN = 'bg-emerald-50 border-emerald-300 text-emerald-700'
const AMBER = 'bg-amber-50 border-amber-300 text-amber-700'
const RED = 'bg-rose-50 border-rose-300 text-rose-700'

const HOUR = 3.6e6
const TPE_OFFSET = 8 * HOUR

// Cron cadences in Taipei time (weekday 0 = Sunday). `hour` is when the job is
// scheduled; warn/stale are hours of tolerated lateness past that (GitHub cron
// routinely starts hours late: TW commits land ~18:30–22:00 for a 14:00 schedule).
export const TW_SCHEDULE = { days: [1, 2, 3, 4, 5], hour: 14, warnLate: 9, staleLate: 30 }
export const ADR_SCHEDULE = { days: [2, 3, 4, 5, 6], hour: 6, warnLate: 6, staleLate: 26 }

export function parseTpe(iso) {
  if (!iso) return null
  // Replace the space with "T" so strict engines (Safari) parse the timestamp.
  const t = Date.parse(String(iso).replace(' ', 'T'))
  return Number.isNaN(t) ? null : t
}

// First scheduled run strictly after `ts` (epoch ms).
export function nextExpected(ts, { days, hour }) {
  const tpe = new Date(ts + TPE_OFFSET) // read with getUTC* = Taipei wall clock
  const midnight = Date.UTC(tpe.getUTCFullYear(), tpe.getUTCMonth(), tpe.getUTCDate()) - TPE_OFFSET
  for (let i = 0; i < 9; i++) {
    const run = midnight + i * 24 * HOUR + hour * HOUR
    const dow = new Date(run + TPE_OFFSET).getUTCDay()
    if (run > ts && days.includes(dow)) return run
  }
  return null
}

/**
 * @param {string} iso  Taipei timestamp, e.g. "2026-05-08 15:25:19+08:00" (or a bare date).
 * @param {object} opts {schedule} or legacy {warnHours, staleHours}; plus {staleNote, now}
 * @returns {{ageHours:number, label:string, cls:string, stale:boolean}|null}
 */
export function computeFreshness(iso, opts = {}) {
  const {
    schedule = null,
    warnHours = 6,
    staleHours = 30,
    staleNote = 'cron 可能失敗',
    now = Date.now(),
  } = opts
  const ts = parseTpe(iso)
  if (ts == null) return null
  const ageHours = (now - ts) / HOUR
  let label
  if (ageHours <= 1) label = `${Math.max(0, Math.round(ageHours * 60))} 分鐘前更新`
  else if (ageHours < 48) label = `${ageHours.toFixed(1)} 小時前更新`
  else label = `${(ageHours / 24).toFixed(1)} 天前更新`

  // Hours overdue relative to the schedule, or plain age without one.
  let late = ageHours
  let warn = warnHours
  let staleAt = staleHours
  if (schedule) {
    const due = nextExpected(ts, schedule)
    late = due == null ? ageHours : (now - due) / HOUR
    warn = schedule.warnLate
    staleAt = schedule.staleLate
  }

  let cls
  let stale = false
  if (late <= warn) {
    cls = GREEN
  } else if (late <= staleAt) {
    cls = AMBER
  } else {
    cls = RED
    stale = true
    label = `${(ageHours / 24).toFixed(1)} 天前 · ${staleNote}`
  }
  return { ageHours, label, cls, stale }
}
