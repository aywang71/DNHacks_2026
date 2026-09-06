import test from 'node:test'
import assert from 'node:assert/strict'
import { HOUR, DAY, dateRange, presetStart, coveredHours, latestPositionedHour, nextCovered, requiredDays, currentObservations, trailFeatures, mergeVessels, createLatestRequest } from '../src/presence/timeline.mjs'
const midnight = Date.parse('2026-08-01T00:00:00Z')
const point = (hour, extra = {}) => ({ vesselId: 'v', ts: new Date(midnight + hour * HOUR).toISOString(), lat: 40, lon: 150 + hour, ...extra })

test('inclusive UTC dates and rolling presets cross month/year/leap boundaries', () => {
  assert.deepEqual(dateRange('2026-08-01', '2026-08-01'), { start: midnight, end: midnight + DAY })
  assert.equal(presetStart('2026-08-01', 7), '2026-07-26')
  assert.equal(presetStart('2026-01-01', 30), '2025-12-03')
  assert.equal(presetStart('2024-03-01', 2), '2024-02-29')
  assert.equal(dateRange('2026-02-30', '2026-03-01'), null)
  assert.equal(dateRange('2026-08-02', '2026-08-01'), null)
  assert.equal(dateRange('', ''), null)
})
test('stepping skips only uncovered hours and stops at the range end', () => {
  const catalog = { days: [{ date: '2026-08-01', coveredHours: [0, 1, 5], hourlyCounts: [1, 0, 0, 0, 0, 2] }] }
  const hours = coveredHours(catalog, dateRange('2026-08-01', '2026-08-01'))
  assert.equal(nextCovered(hours, midnight), midnight + HOUR)
  assert.equal(nextCovered(hours, midnight + HOUR), midnight + 5 * HOUR)
  assert.equal(nextCovered(hours, midnight + 5 * HOUR), null)
  assert.equal(nextCovered(hours, midnight, -1), null)
  assert.equal(nextCovered(hours, midnight + 4 * HOUR, -1), midnight + HOUR)
})
test('initial range selection prefers the latest hour with positions over later empty coverage', () => {
  const catalog = { days: [
    { date: '2026-08-01', coveredHours: [3, 4], hourlyCounts: [0, 0, 0, 8, 0] },
    { date: '2026-08-02', coveredHours: [0, 1], hourlyCounts: [0, 0] },
    { date: '2026-08-03', coveredHours: [2], hourlyCounts: [0, 0, 12] },
  ] }
  assert.equal(latestPositionedHour(catalog, dateRange('2026-08-01', '2026-08-03')), Date.parse('2026-08-03T02:00:00Z'))
  assert.equal(latestPositionedHour(catalog, dateRange('2026-08-01', '2026-08-02')), Date.parse('2026-08-01T03:00:00Z'))
  assert.equal(latestPositionedHour(catalog, dateRange('2026-08-02', '2026-08-02')), Date.parse('2026-08-02T01:00:00Z'))
})
test('cross-midnight trails require only current and preceding imported days', () => {
  const catalog = { days: ['2026-07-30', '2026-07-31', '2026-08-01', '2026-08-02'].map(date => ({ date })) }
  assert.deepEqual(requiredDays(midnight + HOUR, midnight - DAY, catalog).map(day => day.date), ['2026-07-31', '2026-08-01'])
  assert.deepEqual(requiredDays(midnight + HOUR, midnight, catalog).map(day => day.date), ['2026-08-01'])
})
test('selection can persist when current positions disappear; no trail crosses missing hours', () => {
  const rows = [point(0), point(1), point(3)]
  assert.deepEqual(currentObservations(rows, midnight + 2 * HOUR), [])
  assert.equal(trailFeatures(rows, 'v', midnight + 3 * HOUR, midnight).features.length, 1)
  assert.equal(currentObservations(rows, midnight + 3 * HOUR)[0].vesselId, 'v')
})
test('trails span at most six hours and break around multi-cell hours', () => {
  const rows = Array.from({ length: 10 }, (_, i) => point(i))
  assert.equal(trailFeatures(rows, 'v', midnight + 9 * HOUR, midnight).features.length, 6)
  assert.equal(trailFeatures(rows, 'v', midnight + 9 * HOUR, midnight + 7 * HOUR).features.length, 2)
  rows.push(point(8, { lon: 170 }))
  assert.equal(trailFeatures(rows, 'v', midnight + 9 * HOUR, midnight + 7 * HOUR).features.length, 0)
})
test('dateline segments stay short, including equivalent +180/-180 meridians', () => {
  for (const [from, to] of [[179, -179], [-179, 179], [180, -180], [-180, 180]]) {
    const features = trailFeatures([point(0, { lon: from }), point(1, { lon: to, lat: 41 })], 'v', midnight + HOUR, midnight).features
    assert.ok(features.length > 0)
    for (const feature of features) { const [a, b] = feature.geometry.coordinates; assert.ok(a.every(Number.isFinite) && b.every(Number.isFinite)); assert.ok(Math.abs(a[0] - b[0]) <= 2) }
  }
})
test('metadata merge is order independent and retains full selected-range extent', () => {
  const first = { id: 'v', name: 'OLD', metadataRank: '2026|a', firstObservedAt: '2026-08-01T00:00:00Z', lastObservedAt: '2026-08-01T01:00:00Z', observationCount: 2 }
  const second = { ...first, name: 'NEW', metadataRank: '2026|b', firstObservedAt: '2026-08-02T00:00:00Z', lastObservedAt: '2026-08-02T01:00:00Z' }
  const a = mergeVessels([{ vessels: [first] }, { vessels: [second] }]), b = mergeVessels([{ vessels: [second] }, { vessels: [first] }])
  assert.deepEqual(a, b); assert.equal(a[0].name, 'NEW'); assert.equal(a[0].observationCount, 4)
  assert.equal(a[0].firstObservedAt, first.firstObservedAt); assert.equal(a[0].lastObservedAt, second.lastObservedAt)
})
test('late success and late failure cannot overwrite the current request', async () => {
  const gate = createLatestRequest(), values = [], errors = []
  let resolveFirst, rejectSecond
  const first = gate.run(() => new Promise(resolve => { resolveFirst = resolve }), value => values.push(value), error => errors.push(error))
  const second = gate.run(() => new Promise((_, reject) => { rejectSecond = reject }), value => values.push(value), error => errors.push(error))
  await gate.run(async () => 'current', value => values.push(value), error => errors.push(error))
  resolveFirst('old'); rejectSecond(new Error('old failure'))
  await Promise.all([first, second]); assert.deepEqual(values, ['current']); assert.deepEqual(errors, [])
  const pending = gate.run(async () => 'invalidated', value => values.push(value), error => errors.push(error)); gate.invalidate(); await pending
  assert.deepEqual(values, ['current'])
})
