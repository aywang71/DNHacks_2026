import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, stat, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { exportPresence } from '../scripts/export-presence.mjs'
import { workspace, fixture, row, canonical, digest } from './fixtures.mjs'

const read = async filename => JSON.parse(await readFile(filename, 'utf8'))
test('real Bronze reports export 33,452 observations, 25 covered hours, correct first frame', async t => {
  const { output } = await workspace(t)
  const input = fileURLToPath(new URL('../../../data/bronze/gfw_presence', import.meta.url))
  const catalog = await exportPresence({ input, output })
  assert.equal(catalog.observationCount, 33452)
  assert.equal(catalog.coveredHourCount, 25)
  assert.equal(catalog.days.length, 2)
  assert.deepEqual(catalog.days[0].coveredHours, [0])
  const latest = catalog.days[1]
  assert.equal(latest.vesselCount, 1973)
  assert.equal(latest.hourlyCounts[0], 1184)
  assert.equal(latest.hourlyCounts[23], 1280)
  const observations = (await read(path.join(output, latest.observationsUrl))).observations
  assert.equal(observations.length, 31477)
  assert.ok(observations.every((entry, index) => !index || observations[index - 1].ts <= entry.ts))
})

test('identical/reordered reports dedupe; latest metadata wins; distinct cells survive', async t => {
  const options = await workspace(t)
  await fixture(options.input, 'old', [row(), row('2026-08-01 01:00')])
  await fixture(options.input, 'new', [row('2026-08-01 01:00', { shipName: 'NEW' }), row(undefined, { shipName: 'NEW', lon: 158.64 }), row(undefined, { lon: 159 })], { manifest: { created_at: '2026-09-06T00:00:00Z' } })
  await fixture(options.input, 'copy', [row(), row('2026-08-01 01:00')])
  const catalog = await exportPresence(options)
  assert.equal(catalog.observationCount, 3)
  const positions = (await read(path.join(options.output, catalog.days[0].observationsUrl))).observations
  assert.equal(positions.filter(p => p.ts.endsWith('00:00:00.000Z')).length, 2)
  assert.ok(positions.every(p => p.ts.startsWith('2026-08-01')))
  const summary = await read(path.join(options.output, catalog.days[0].vesselsUrl))
  assert.equal(summary.vessels[0].name, 'NEW')
  assert.equal(summary.vessels[0].mmsi, null)
  assert.equal(summary.vessels[0].imo, null)
  assert.equal(summary.vessels[0].id, 'gfw:vessel-a')
})

test('imported empty hours preserve coverage; missing hours stay uncovered', async t => {
  const options = await workspace(t)
  await fixture(options.input, 'empty', [], { start: '2026-08-01T04:00:00Z', end: '2026-08-01T06:00:00Z' })
  const catalog = await exportPresence(options)
  assert.deepEqual(catalog.days[0].coveredHours, [4, 5])
  assert.deepEqual(catalog.days[0].hourlyCounts, Array(24).fill(0))
  assert.equal(catalog.days[0].bounds, null)
})

test('new report extends catalog and published immutable assets are not rewritten', async t => {
  const options = await workspace(t)
  await fixture(options.input, 'first', [row()])
  const first = await exportPresence(options)
  const asset = path.join(options.output, first.days[0].observationsUrl)
  const before = await stat(asset)
  await fixture(options.input, 'second', [row('2026-08-02 01:00')], { start: '2026-08-02T00:00:00Z', end: '2026-08-03T00:00:00Z' })
  const second = await exportPresence(options)
  assert.equal(second.days.length, 2); assert.equal(second.coveredHourCount, 48)
  assert.notEqual(first.revision, second.revision)
  assert.equal((await stat(asset)).mtimeMs, before.mtimeMs)
  assert.equal((await read(asset)).observations.length, 1)
})

for (const [name, rows, options] of [
  ['unfinished pagination even at zero', [row()], { envelope: { nextOffset: 0 } }],
  ['bad envelope total', [row()], { envelope: { total: 2 } }],
  ['empty dataset object', [], { envelope: { entries: [{}] } }],
  ['wrong empty dataset', [], { envelope: { entries: [{ 'public-global-presence:v99': [] }] } }],
  ['invalid calendar date', [row('2026-02-30 00:00')], {}],
  ['non-hourly timestamp', [row('2026-08-01 00:30')], {}],
  ['outside request', [row('2026-08-02 00:00')], {}],
  ['invalid coordinates', [row(undefined, { lat: 91 })], {}],
  ['missing GFW identity', [row(undefined, { vesselId: '' })], {}],
  ['unsupported resolution', [row()], { request: { 'temporal-resolution': 'DAILY' } }],
  ['wrong manifest row count', [row()], { manifest: { row_count: 2 } }],
  ['corrupt hash', [row()], { manifest: { raw_response_sha256: '0'.repeat(64) } }],
]) test(`reject ${name} and retain previous catalog`, async t => {
  const paths = await workspace(t)
  await fixture(paths.input, 'valid', [row()])
  await exportPresence(paths)
  const old = await readFile(path.join(paths.output, 'catalog.json'), 'utf8')
  const invalid = await fixture(paths.input, 'invalid', rows, options)
  await assert.rejects(exportPresence(paths), error => error.message.includes(invalid.report))
  assert.equal(await readFile(path.join(paths.output, 'catalog.json'), 'utf8'), old)
})

test('preserves Python numeric spelling when checking manifest hashes', async t => {
  const paths = await workspace(t)
  const source = await fixture(paths.input, 'float', [row()])
  const raw = JSON.stringify(canonical(source.payload)).replace('"lat":53', '"lat":53.0')
  await writeFile(source.report, raw)
  await writeFile(source.manifestFile, JSON.stringify({ ...source.metadata, raw_response_sha256: digest(raw) }))
  assert.equal((await exportPresence(paths)).observationCount, 1)
})

test('CLI imports fixtures without credentials', async t => {
  const paths = await workspace(t)
  await fixture(paths.input, 'source', [row()])
  const stdout = execFileSync(process.execPath, [fileURLToPath(new URL('../scripts/export-presence.mjs', import.meta.url)), '--input', paths.input, '--output', paths.output], { encoding: 'utf8', env: { ...process.env, GFW_API_TOKEN: '' } })
  assert.match(stdout, /Exported 1 observations across 24 covered hours/)
})
