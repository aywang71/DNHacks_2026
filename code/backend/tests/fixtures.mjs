import { createHash } from 'node:crypto'
import { mkdir, mkdtemp, writeFile, rm } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const backend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const dataset = 'public-global-presence:v4.0'
export const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value
export const digest = value => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(canonical(value))).digest('hex')
export const row = (date = '2026-08-01 00:00', extra = {}) => ({ vesselId: 'vessel-a', date, entryTimestamp: '2020-01-01T00:00:00Z', lastTransmissionDate: '2026-09-01T00:00:00Z', lat: 53, lon: 158.63999938964844, hours: 1, shipName: 'TEST', flag: 'RUS', mmsi: '', imo: '', ...extra })
export async function workspace(t) {
  const root = path.join(backend, '.test-output')
  await mkdir(root, { recursive: true })
  const directory = await mkdtemp(path.join(root, 'presence-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const input = path.join(directory, 'input'), output = path.join(directory, 'output')
  await mkdir(input)
  return { input, output }
}
export async function fixture(input, name, rows, { manifest = {}, request = {}, envelope = {}, start = '2026-08-01T00:00:00Z', end = '2026-08-02T00:00:00Z' } = {}) {
  const directory = path.join(input, name)
  await mkdir(directory, { recursive: true })
  const payload = { entries: [{ [dataset]: rows }], total: 1, nextOffset: null, offset: null, limit: null, ...envelope }
  const metadata = { created_at: '2026-09-05T00:00:00Z', dataset_version: dataset, raw_response_path: 'does\\not\\exist', row_count: rows.length, raw_response_sha256: digest(payload),
    request: { 'temporal-resolution': 'HOURLY', 'spatial-resolution': 'HIGH', 'spatial-aggregation': false, 'group-by': 'VESSEL_ID', 'region-dataset': 'public-eez-areas', 'region-id': 5690, 'date-range': `${start},${end}`, ...request }, ...manifest }
  const report = path.join(directory, 'report.json'), manifestFile = path.join(directory, 'manifest.json')
  await writeFile(report, JSON.stringify(payload, null, 2)); await writeFile(manifestFile, JSON.stringify(metadata, null, 2))
  return { report, manifestFile, payload, metadata }
}
