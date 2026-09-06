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

// Prefer a populated observation hour whenever a range is opened. Catalog
// coverage can include deliberately imported empty hours, which are useful for
// playback but make a poor initial view.
export function latestPositionedHour(catalog, range) {
  let latestPosition = null
  let latestCovered = null
  for (const day of catalog.days) {
    const midnight = Date.parse(`${day.date}T00:00:00Z`)
    for (const hour of day.coveredHours) {
      const timestamp = midnight + hour * HOUR
      if (timestamp < range.start || timestamp >= range.end) continue
      if (latestCovered === null || timestamp > latestCovered) latestCovered = timestamp
      if (day.hourlyCounts[hour] > 0 && (latestPosition === null || timestamp > latestPosition)) latestPosition = timestamp
    }
  }
  return latestPosition ?? latestCovered
}

export function earliestPositionedHour(catalog, range) {
  let earliestPosition = null
  let earliestCovered = null
  for (const day of catalog.days) {
    const midnight = Date.parse(`${day.date}T00:00:00Z`)
    for (const hour of day.coveredHours) {
      const timestamp = midnight + hour * HOUR
      if (timestamp < range.start || timestamp >= range.end) continue
      if (earliestCovered === null || timestamp < earliestCovered) earliestCovered = timestamp
      if (day.hourlyCounts[hour] > 0 && (earliestPosition === null || timestamp < earliestPosition)) earliestPosition = timestamp
    }
  }
  return earliestPosition ?? earliestCovered
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
  const dates = new Set([dayOf(cursor), dayOf(cursor + HOUR), dayOf(Math.max(rangeStart, cursor - 6 * HOUR))])
  return catalog.days.filter(day => dates.has(day.date))
}

export function currentObservations(observations, cursor) {
  return observations.filter(row => Date.parse(row.ts) === cursor)
}

// Blend consecutive hourly reports into animation frames. Vessels with a
// report at only one end of the interval fade in/out, avoiding a distracting
// pop when the set of reporting vessels changes.
export function createObservationInterpolator(current, next) {
  // Match reports once per interval, rather than rebuilding indexes every frame.
  const currentCounts = new Map(), nextCounts = new Map(), nextByVessel = new Map()
  for (const row of current) currentCounts.set(row.vesselId, (currentCounts.get(row.vesselId) ?? 0) + 1)
  for (const row of next) {
    nextCounts.set(row.vesselId, (nextCounts.get(row.vesselId) ?? 0) + 1)
    nextByVessel.set(row.vesselId, row)
  }
  const matched = new Set()
  const pairs = current.map(row => {
    const target = nextByVessel.get(row.vesselId)
    if (!target || currentCounts.get(row.vesselId) !== 1 || nextCounts.get(row.vesselId) !== 1) return { row }
    matched.add(row.vesselId)
    let longitudeDelta = target.lon - row.lon
    if (longitudeDelta > 180) longitudeDelta -= 360
    if (longitudeDelta < -180) longitudeDelta += 360
    return { row, target, longitudeDelta }
  })
  const joining = next.filter(row => !matched.has(row.vesselId))
  return progress => {
    if (progress <= 0) return current.map(row => ({ ...row, opacity: 1 }))
    if (progress >= 1) return next.map(row => ({ ...row, opacity: 1 }))
    // Constant speed avoids braking and accelerating at every hourly report.
    const t = progress
    const fade = t * t * (3 - 2 * t)
    const frames = pairs.map(({ row, target, longitudeDelta }) => {
      if (!target) return { ...row, opacity: 1 - fade }
      let lon = row.lon + longitudeDelta * t
      if (lon > 180) lon -= 360
      if (lon < -180) lon += 360
      return { ...row, lat: row.lat + (target.lat - row.lat) * t, lon, opacity: 1 }
    })
    for (const row of joining) frames.push({ ...row, opacity: fade })
    return frames
  }
}

export function interpolateObservations(current, next, progress) {
  return createObservationInterpolator(current, next)(progress)
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
