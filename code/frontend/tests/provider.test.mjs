import test from 'node:test'
import assert from 'node:assert/strict'
import { createPresenceProvider } from '../src/presence/provider.mjs'
import { dateRange } from '../src/presence/timeline.mjs'
const days = [1, 2, 3, 4].map(n => ({ date: `2026-08-0${n}`, observationsUrl: `obs${n}.json`, vesselsUrl: `vessels${n}.json` }))

test('day cache retains three most recently used shards', async () => {
  const calls = []
  const provider = createPresenceProvider('/presence/', async url => { calls.push(url); return Response.json({ observations: [] }) })
  await provider.getDay(days[0]); await provider.getDay(days[1]); await provider.getDay(days[2]); await provider.getDay(days[0]); await provider.getDay(days[3]); await provider.getDay(days[1])
  assert.deepEqual(calls, ['/presence/obs1.json', '/presence/obs2.json', '/presence/obs3.json', '/presence/obs4.json', '/presence/obs2.json'])
})
test('range search fetches only relevant lightweight indexes', async () => {
  const calls = []
  const provider = createPresenceProvider('/presence/', async url => { calls.push(url); return Response.json({ vessels: [] }) })
  assert.deepEqual(await provider.getVessels({ days }, dateRange('2026-08-02', '2026-08-03')), [])
  assert.deepEqual(calls.sort(), ['/presence/vessels2.json', '/presence/vessels3.json'])
})
test('aborted responses are discarded and cannot warm the cache', async () => {
  const abort = new AbortController(); let calls = 0
  const provider = createPresenceProvider('/', async () => { calls++; if (calls === 1) abort.abort(); return Response.json({ observations: [] }) })
  await assert.rejects(provider.getDay(days[0], abort.signal), { name: 'AbortError' })
  await provider.getDay(days[0]); assert.equal(calls, 2)
})
test('missing catalog, HTML fallback, and failed day fetch expose retryable errors', async () => {
  await assert.rejects(createPresenceProvider('/', async () => new Response('', { status: 404 })).getCatalog(), /Retry to reconnect/)
  await assert.rejects(createPresenceProvider('/', async () => new Response('<html>')).getCatalog(), /import again/)
  let calls = 0
  const provider = createPresenceProvider('/', async () => ++calls === 1 ? new Response('', { status: 503 }) : Response.json({ observations: [] }))
  await assert.rejects(provider.getDay(days[0]), /Retry/)
  assert.deepEqual(await provider.getDay(days[0]), { observations: [] })
})
