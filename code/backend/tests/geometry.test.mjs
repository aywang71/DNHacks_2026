import test from 'node:test'
import assert from 'node:assert/strict'
import { circularBounds } from '../src/presence/geometry.mjs'

test('daily bounds use the short arc across the dateline', () => {
  assert.deepEqual(circularBounds([{ lon: 179, lat: 40 }, { lon: -179, lat: 41 }]), [179, 40, 181, 41])
  assert.equal(circularBounds([]), null)
})

test('daily bounds handle large reports without overflowing function arguments', () => {
  assert.deepEqual(circularBounds(Array.from({ length: 150000 }, () => ({ lon: 1, lat: 2 }))), [1, 2, 1, 2])
})
