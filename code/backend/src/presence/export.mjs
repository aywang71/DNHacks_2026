import { mkdir, writeFile, rename, access } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { HOUR, hash, readPresence } from './source.mjs'
import { circularBounds } from './geometry.mjs'

const backend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const dayOf = timestamp => new Date(timestamp).toISOString().slice(0, 10)

/** Prepare immutable daily assets and atomically publish their catalog. */
export async function exportPresence({
  input = path.resolve(backend, '../../data/bronze/gfw_presence'),
  output = path.resolve(backend, '../frontend/public/data/presence'),
} = {}) {
  const { observations, coverages } = await readPresence(input)
  const days = new Map()
  function day(date) { if (!days.has(date)) days.set(date, { date, covered: new Set(), observations: [], vessels: new Map() }); return days.get(date) }
  const coverage = [...coverages.values()].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)))
  for (const interval of coverage) for (let ts = Date.parse(interval.start); ts < Date.parse(interval.end); ts += HOUR) day(dayOf(ts)).covered.add(new Date(ts).getUTCHours())
  for (const { observation, vessel, rank } of observations.values()) {
    const target = day(observation.ts.slice(0, 10)); target.observations.push(observation)
    const previous = target.vessels.get(vessel.id)
    target.vessels.set(vessel.id, {
      ...(previous && previous.rank > rank ? previous : { ...vessel, rank }),
      firstObservedAt: previous && previous.firstObservedAt < observation.ts ? previous.firstObservedAt : observation.ts,
      lastObservedAt: previous && previous.lastObservedAt > observation.ts ? previous.lastObservedAt : observation.ts,
      observationCount: (previous?.observationCount ?? 0) + 1,
    })
  }
  const assets = new Map()
  function asset(prefix, value) { const body = JSON.stringify(value); const url = `${prefix}.${hash(body)}.json`; assets.set(url, body); return url }
  const catalogDays = [...days.values()].sort((a, b) => a.date.localeCompare(b.date)).map(target => {
    const rows = target.observations.sort((a, b) => a.ts.localeCompare(b.ts) || a.id.localeCompare(b.id))
    const vessels = [...target.vessels.values()].sort((a, b) => a.id.localeCompare(b.id)).map(({ rank, ...vessel }) => vessel)
    const hourlyCounts = Array(24).fill(0)
    for (const row of rows) hourlyCounts[new Date(row.ts).getUTCHours()]++
    return { date: target.date, observationsUrl: asset(`${target.date}.observations`, { date: target.date, observations: rows }), vesselsUrl: asset(`${target.date}.vessels`, { date: target.date, vessels }),
      bounds: circularBounds(rows), coveredHours: [...target.covered].sort((a, b) => a - b), hourlyCounts, observationCount: rows.length, vesselCount: vessels.length }
  })
  const content = { schemaVersion: 1, source: 'Global Fishing Watch', positionSemantics: 'gfw_presence_grid_center_hourly', coverage, days: catalogDays,
    observationCount: observations.size, coveredHourCount: catalogDays.reduce((sum, entry) => sum + entry.coveredHours.length, 0) }
  const catalog = { ...content, revision: hash(content), generatedAt: new Date().toISOString() }
  await mkdir(output, { recursive: true })
  // Old immutable assets remain valid for tabs still using the previous catalog.
  for (const [filename, body] of assets) {
    const destination = path.join(output, filename)
    try { await access(destination); continue } catch (error) { if (error.code !== 'ENOENT') throw error }
    const temporaryAsset = `${destination}.${process.pid}.${Date.now()}.tmp`
    await writeFile(temporaryAsset, body)
    await rename(temporaryAsset, destination)
  }
  const temporary = path.join(output, `.catalog-${process.pid}-${Date.now()}.tmp`)
  await writeFile(temporary, JSON.stringify(catalog, null, 2))
  await rename(temporary, path.join(output, 'catalog.json'))
  return catalog
}
