import { dayOf, mergeVessels } from './timeline.mjs'

export function createPresenceProvider(base = '/data/presence/', fetcher = globalThis.fetch.bind(globalThis)) {
  const root = base.endsWith('/') ? base : `${base}/`
  const observations = new Map(), summaries = new Map()
  let revision = null
  async function read(filename, signal, cache, limit = 3) {
    if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
    if (cache?.has(filename)) { const result = cache.get(filename); cache.delete(filename); cache.set(filename, result); return result }
    const response = await fetcher(`${root}${filename}`, { signal, cache: filename === 'catalog.json' ? 'no-store' : 'default' })
    if (!response.ok) throw new Error(filename === 'catalog.json' ? 'Presence data is unavailable. Run npm run import:presence from code/frontend, then retry.' : 'This day could not be loaded. Retry to load its observations.')
    let result
    try { result = await response.json() } catch { throw new Error('Presence assets could not be read. Run the import again, then retry.') }
    if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
    if (cache) { cache.set(filename, result); while (cache.size > limit) cache.delete(cache.keys().next().value) }
    return result
  }
  const provider = {
    async getCatalog(signal) {
      const catalog = await read('catalog.json', signal)
      if (catalog.schemaVersion !== 1 || !Array.isArray(catalog.days) || !catalog.days.length) throw new Error('No supported presence catalog is available. Run the import again, then retry.')
      if (revision !== catalog.revision) { observations.clear(); summaries.clear(); revision = catalog.revision }
      return catalog
    },
    async getDay(day, signal) { return read(day.observationsUrl, signal, observations) },
    async getVessels(catalog, range, signal) {
      const days = catalog.days.filter(day => day.date >= dayOf(range.start) && day.date <= dayOf(range.end - 1))
      const result = new Array(days.length)
      let index = 0
      await Promise.all(Array.from({ length: Math.min(4, days.length) }, async () => {
        while (index < days.length) { const current = index++; result[current] = await read(days[current].vesselsUrl, signal, summaries, 64) }
      }))
      return mergeVessels(result)
    },
    prefetchDay(day) { void provider.getDay(day).catch(() => { /* Foreground requests expose retryable failures. */ }) },
  }
  return provider
}
