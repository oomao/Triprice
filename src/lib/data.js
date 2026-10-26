// Shared loader for the daily data/*.json files.
//
// Python's json.dump writes a bare `NaN` for a missing float unless told not to.
// In 2026-10 a NaN ADR close made 2330/2303/3711.json unparseable, which took down
// the whole stock page, the /adr dashboard and three screener rows. The fetchers
// now refuse to write NaN, but the page must not depend on that: map NaN/Infinity
// tokens (only in value position, never inside strings) to null before parsing.
//
// Responses are memoised for a few minutes so hopping list → stock → list doesn't
// refetch the same 26 files; the service worker still decides network vs cache.

const BASE = import.meta.env.BASE_URL
const TTL_MS = 5 * 60 * 1000
const cache = new Map() // path -> { at, promise }

const NON_FINITE = /([:[,]\s*)-?(?:NaN|Infinity)\b/g

export function parseLenient(text) {
  return JSON.parse(text.replace(NON_FINITE, '$1null'))
}

/**
 * @param {string} path relative to data/, e.g. 'stocks.json' or 'tw/2330.json'
 * @param {{optional?: boolean}} opts optional → resolve null on 404 instead of throwing
 */
export function fetchData(path, { optional = false } = {}) {
  const hit = cache.get(path)
  if (hit && Date.now() - hit.at < TTL_MS) return hit.promise
  const promise = fetch(`${BASE}data/${path}`)
    .then(async (res) => {
      if (!res.ok) {
        if (optional) return null
        throw new Error(`${path}: HTTP ${res.status}`)
      }
      return parseLenient(await res.text())
    })
    .catch((e) => {
      cache.delete(path) // don't memoise failures
      if (optional) return null
      throw e
    })
  cache.set(path, { at: Date.now(), promise })
  return promise
}
