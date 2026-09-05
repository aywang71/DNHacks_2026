import { createHash } from 'node:crypto'
import { readdir, readFile, mkdir, writeFile, rename, access } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { HOUR, dayOf, circularBounds } from '../src/presence/timeline.mjs'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const hash = value => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex')
const text = value => value == null || String(value).trim() === '' ? null : String(value).trim()
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value

// Preserve original numeric tokens (including Python's 1.0 and 1e-07),
// normalize string escaping, sort object keys, and discard whitespace.
// JSON.parse validates the input before this canonical integrity check.
function sourceCanonicalJSON(raw) {
  const tokens = raw.match(/"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\]:,]/g)
  let index = 0
  const quote = value => JSON.stringify(value).replace(/[\u007f-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`)
  function value() {
    const token = tokens[index++]
    if (token === '{') {
      const pairs = []
      while (tokens[index] !== '}') {
        const key = JSON.parse(tokens[index++]); index++
        pairs.push([key, value()])
        if (tokens[index] === ',') index++
      }
      index++; return `{${pairs.sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0).map(([key, entry]) => `${quote(key)}:${entry}`).join(',')}}`
    }
    if (token === '[') {
      const entries = []
      while (tokens[index] !== ']') { entries.push(value()); if (tokens[index] === ',') index++ }
      index++; return `[${entries.join(',')}]`
    }
    return token.startsWith('"') ? quote(JSON.parse(token)) : token
  }
  return value()
}

async function discover(directory) {
  const found = []
  for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
    const target = path.join(directory, entry.name)
    if (entry.isDirectory()) found.push(...await discover(target))
    else if (entry.name === 'report.json') found.push(target)
  }
  return found
}

function assert(condition, message) { if (!condition) throw new Error(message) }
function utcHour(value) {
  assert(typeof value === 'string' && /^\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::00(?:\.000)?)?(?:Z)?$/.test(value), `Invalid UTC hour: ${value}`)
  const normalized = value.replace(' ', 'T').replace(/Z$/, '')
  const ts = Date.parse(`${normalized}Z`)
  assert(Number.isFinite(ts) && ts % HOUR === 0 && new Date(ts).toISOString().slice(0, 16) === normalized.slice(0, 16), `Invalid UTC hour: ${value}`)
  return ts
}

function readRows(payload, expectedDataset) {
  assert(payload && Array.isArray(payload.entries), 'Missing report entries array')
  assert(payload.nextOffset == null && (payload.offset == null || payload.offset === 0), 'Incomplete paginated report')
  // 4Wings total counts dataset envelopes, not observation rows.
  assert(payload.total == null || payload.total === payload.entries.length, 'Report envelope total does not match entries')
  const rows = []
  for (const entry of payload.entries) {
    assert(entry && typeof entry === 'object' && !Array.isArray(entry), 'Invalid dataset envelope')
    assert(Object.keys(entry).length > 0, 'Empty dataset envelope')
    for (const [datasetVersion, values] of Object.entries(entry)) {
      assert(datasetVersion.startsWith('public-global-presence:') && Array.isArray(values), 'Unsupported presence dataset envelope')
      assert(datasetVersion === expectedDataset, 'Dataset version differs from manifest')
      for (const row of values) { assert(row && typeof row === 'object' && !Array.isArray(row), 'Invalid observation row'); rows.push({ datasetVersion, row }) }
    }
  }
  return rows
}

export async function exportPresence({ input = path.resolve(frontend, '../../data/bronze/gfw_presence'), output = path.join(frontend, 'public/data/presence') } = {}) {
  const files = await discover(input)
  assert(files.length > 0, `No presence report.json files found in ${input}`)
  const observations = new Map(), coverages = new Map(), parsedPayloads = new Map()
  for (const file of files) {
    try {
      const raw = await readFile(file, 'utf8')
      const payload = JSON.parse(raw)
      const manifest = JSON.parse(await readFile(path.join(path.dirname(file), 'manifest.json'), 'utf8'))
      const request = manifest.request ?? {}
      assert(request['temporal-resolution'] === 'HOURLY' && request['spatial-aggregation'] === false && request['group-by'] === 'VESSEL_ID', 'Requires unaggregated HOURLY VESSEL_ID presence report')
      const gridResolution = { HIGH: 0.01, LOW: 0.1 }[request['spatial-resolution']]
      assert(gridResolution, 'Unsupported spatial resolution')
      assert(typeof request['region-dataset'] === 'string' && Number.isInteger(request['region-id']), 'Missing region identity')
      const range = request['date-range']?.split(',')
      assert(range?.length === 2, 'Missing requested date range')
      const start = utcHour(range[0]), end = utcHour(range[1])
      assert(start < end, 'Requested range must have start before end')
      assert(typeof manifest.dataset_version === 'string' && manifest.dataset_version.startsWith('public-global-presence:'), 'Missing presence dataset version')
      const updated = Date.parse(manifest.created_at)
      assert(Number.isFinite(updated), 'Missing valid retrieval creation time')
      const rank = `${new Date(updated).toISOString()}|${path.relative(input, file)}`
      // Compute our own canonical fingerprint. Upstream hashes use Python JSON
      // number formatting and must not be compared to raw file bytes or JS JSON.
      const fingerprint = hash(canonical(payload))
      if (manifest.raw_response_sha256 != null) {
        assert(/^[a-f0-9]{64}$/.test(manifest.raw_response_sha256), 'Invalid manifest payload hash')
        assert(manifest.raw_response_sha256 === fingerprint || manifest.raw_response_sha256 === hash(sourceCanonicalJSON(raw)), 'Manifest payload hash does not match report contents')
      }
      let rows = parsedPayloads.get(fingerprint)
      if (!rows) { rows = readRows(payload, manifest.dataset_version); parsedPayloads.set(fingerprint, rows) }
      else readRows(payload, manifest.dataset_version)
      assert(Number.isInteger(manifest.row_count) && manifest.row_count === rows.length, 'Manifest row_count does not match report')
      assert(manifest.valid_position_count == null || manifest.valid_position_count === rows.length, 'Manifest reports invalid positions')
      const coverage = { start: new Date(start).toISOString(), end: new Date(end).toISOString(), regionDataset: request['region-dataset'], regionId: request['region-id'], datasetVersion: manifest.dataset_version, gridResolution }
      coverages.set(JSON.stringify(coverage), coverage)
      for (const { datasetVersion, row } of rows) {
        const timestamp = utcHour(row.date)
        assert(timestamp >= start && timestamp < end, `Observation ${row.date} is outside requested range`)
        assert(datasetVersion === manifest.dataset_version, 'Dataset version differs from manifest')
        assert(typeof row.vesselId === 'string' && text(row.vesselId), 'Missing GFW vessel identity')
        assert(typeof row.lat === 'number' && Number.isFinite(row.lat) && Math.abs(row.lat) <= 90 && typeof row.lon === 'number' && Number.isFinite(row.lon) && Math.abs(row.lon) <= 180, 'Invalid position coordinates')
        assert(typeof row.hours === 'number' && Number.isFinite(row.hours) && row.hours >= 0 && row.hours <= 1, 'Invalid hourly presence duration')
        const vesselId = `gfw:${text(row.vesselId)}`
        const cellLat = Math.round(row.lat / gridResolution), cellLon = Math.round(row.lon / gridResolution)
        const id = hash([datasetVersion, gridResolution, vesselId, timestamp, cellLat, cellLon])
        const recordRank = `${rank}|${new Date(timestamp).toISOString()}|${hash(canonical(row))}`
        const previous = observations.get(id)
        if (previous && previous.rank >= recordRank) continue
        observations.set(id, {
          rank: recordRank,
          observation: { id, vesselId, ts: new Date(timestamp).toISOString(), lat: row.lat, lon: row.lon, presenceHours: row.hours, datasetVersion, gridResolution },
          vessel: { id: vesselId, name: text(row.shipName), mmsi: text(row.mmsi), imo: text(row.imo), callsign: text(row.callsign), flag: text(row.flag), vesselType: text(row.vesselType), metadataUpdatedAt: new Date(updated).toISOString(), metadataRank: recordRank },
        })
      }
    } catch (error) { throw new Error(`${file}: ${error.message}`, { cause: error }) }
  }

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

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), options = {}
  for (let i = 0; i < args.length; i += 2) {
    if (!['--input', '--output'].includes(args[i]) || !args[i + 1]) throw new Error('Usage: npm run import:presence -- [--input directory] [--output directory]')
    options[args[i].slice(2)] = path.resolve(args[i + 1])
  }
  try { const result = await exportPresence(options); console.log(`Exported ${result.observationCount.toLocaleString('en-US')} observations across ${result.coveredHourCount} covered hours (${result.days.length} UTC days).`) }
  catch (error) { console.error(error.message); process.exitCode = 1 }
}
