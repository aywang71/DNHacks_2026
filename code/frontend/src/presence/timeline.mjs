export const HOUR = 3_600_000
export const DAY = 24 * HOUR
export const dayOf = (timestamp) => new Date(timestamp).toISOString().slice(0, 10)

export function dateRange(startDate, endDate) {
  const start = Date.parse(`${startDate}T00:00:00Z`)
  const end = Date.parse(`${endDate}T00:00:00Z`) + DAY
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end || dayOf(start) !== startDate || dayOf(end - DAY) !== endDate) return null
  return { start, end }
}

export function presetStart(endDate, days) {
  return dayOf(Date.parse(`${endDate}T00:00:00Z`) - (days - 1) * DAY)
}

export function coveredHours(catalog, range) {
  return catalog.days.flatMap(day => day.coveredHours.map(hour => Date.parse(`${day.date}T00:00:00Z`) + hour * HOUR))
    .filter(ts => ts >= range.start && ts < range.end).sort((a, b) => a - b)
}

export function nextCovered(hours, cursor, direction = 1) {
  // Binary search keeps stepping independent of the size of the archive.
  let lo = 0, hi = hours.length
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (hours[mid] <= cursor) lo = mid + 1; else hi = mid }
  if (direction > 0) return hours[lo] ?? null
  const index = lo - 1
  return hours[index] === cursor ? hours[index - 1] ?? null : hours[index] ?? null
}

export function requiredDays(cursor, rangeStart, catalog) {
  const dates = new Set([dayOf(cursor), dayOf(Math.max(rangeStart, cursor - 6 * HOUR))])
  return catalog.days.filter(day => dates.has(day.date))
}

export function currentObservations(observations, cursor) {
  return observations.filter(row => Date.parse(row.ts) === cursor)
}

export function trailFeatures(observations, vesselId, cursor, rangeStart) {
  if (!vesselId) return { type: 'FeatureCollection', features: [] }
  const start = Math.max(rangeStart, cursor - 6 * HOUR)
  const buckets = new Map()
  for (const row of observations) {
    if (row.vesselId !== vesselId) continue
    const ts = Date.parse(row.ts)
    if (ts < start || ts > cursor) continue
    const bucket = buckets.get(ts) ?? []; bucket.push(row); buckets.set(ts, bucket)
  }
  const features = []
  for (const [ts, rows] of buckets) {
    const next = buckets.get(ts + HOUR)
    if (rows.length !== 1 || next?.length !== 1) continue
    const a = [rows[0].lon, rows[0].lat], b = [next[0].lon, next[0].lat]
    const lines = []
    if (Math.abs(a[0] - b[0]) <= 180) lines.push([a, b])
    else {
      const shifted = b[0] + (a[0] > 0 ? 360 : -360)
      if (shifted === a[0]) lines.push([a, [a[0], b[1]]])
      else {
        const edge = a[0] > 0 ? 180 : -180
        const lat = a[1] + (b[1] - a[1]) * (edge - a[0]) / (shifted - a[0])
        lines.push([a, [edge, lat]], [[-edge, lat], b])
      }
    }
    for (const coordinates of lines) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates } })
  }
  return { type: 'FeatureCollection', features }
}

export function circularBounds(points) {
  if (!points.length) return null
  const lons = [...new Set(points.map(p => ((p.lon % 360) + 360) % 360))].sort((a, b) => a - b)
  let gap = -1, after = 0
  for (let i = 0; i < lons.length; i++) {
    const distance = (i + 1 < lons.length ? lons[i + 1] : lons[0] + 360) - lons[i]
    if (distance > gap) { gap = distance; after = (i + 1) % lons.length }
  }
  let west = lons[after], east = west + 360 - gap
  if (west > 180) { west -= 360; east -= 360 }
  let south = 90, north = -90
  for (const point of points) { south = Math.min(south, point.lat); north = Math.max(north, point.lat) }
  return [west, south, east, north]
}

export function mergeVessels(summaries) {
  const merged = new Map()
  for (const summary of summaries) for (const vessel of summary.vessels) {
    const previous = merged.get(vessel.id)
    if (!previous) merged.set(vessel.id, { ...vessel })
    else {
      const latest = vessel.metadataRank > previous.metadataRank ? vessel : previous
      merged.set(vessel.id, { ...latest, firstObservedAt: previous.firstObservedAt < vessel.firstObservedAt ? previous.firstObservedAt : vessel.firstObservedAt,
        lastObservedAt: previous.lastObservedAt > vessel.lastObservedAt ? previous.lastObservedAt : vessel.lastObservedAt,
        observationCount: previous.observationCount + vessel.observationCount })
    }
  }
  return [...merged.values()].sort((a, b) => (a.name ?? a.id).localeCompare(b.name ?? b.id))
}

// Shared by React effects and tests: superseded responses cannot publish state.
export function createLatestRequest() {
  let sequence = 0
  return {
    invalidate() { sequence++ },
    async run(work, publish, reject) {
      const own = ++sequence
      try { const value = await work(); if (own === sequence) publish(value) }
      catch (error) { if (own === sequence) reject(error) }
    },
  }
}
