import { readFile } from 'node:fs/promises'
import path from 'node:path'

export class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

const HOUR = 3_600_000
const DAY = 24 * HOUR
const iso = value => new Date(value).toISOString()

export function validateRequest(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new HttpError(400, 'Send a ship and a date range.')
  if (typeof body.vesselId !== 'string' || !body.vesselId.trim() || body.vesselId.length > 200) throw new HttpError(400, 'Choose a valid ship.')
  if (body.caseId != null && (typeof body.caseId !== 'string' || body.caseId.length > 300)) throw new HttpError(400, 'Choose a valid investigation.')
  const notes = body.notes ?? ''
  if (typeof notes !== 'string' || notes.length > 8000) throw new HttpError(400, 'Keep additional context under 8,000 characters.')
  const messages = body.messages ?? []
  if (!Array.isArray(messages) || messages.length > 12 || messages.some((message, index) => !message || message.role !== (index % 2 ? 'assistant' : 'user') || typeof message.content !== 'string' || !message.content.trim() || message.content.length > 12000)) throw new HttpError(400, 'Send up to six alternating question and answer turns.')
  if (messages.reduce((total, message) => total + message.content.length, 0) > 48000) throw new HttpError(400, 'This conversation is too long. Start a new chat.')
  return { vesselId: body.vesselId, caseId: body.caseId, start: body.start, end: body.end, notes, messages }
}

// Only local exported assets are read. Client text cannot choose a file or URL.
export function createContextLoader(dataRoot) {
  async function read(relative) {
    const filename = path.resolve(dataRoot, relative)
    if (!filename.startsWith(path.resolve(dataRoot) + path.sep)) throw new HttpError(500, 'Invalid data asset path.')
    try { return JSON.parse(await readFile(filename, 'utf8')) }
    catch { throw new HttpError(503, 'Ship data could not be loaded. Rebuild the presence and investigation exports, then retry.') }
  }
  return async function loadContext(request) {
    let investigation = null
    let start = request.start, end = request.end
    if (request.caseId) {
      const queue = await read('investigations/queue.json')
      const batch = queue.batches.find(batch => batch.items.some(item => item.id === request.caseId && item.vesselId === request.vesselId))
      if (!batch) throw new HttpError(404, 'This investigation is no longer in the exported queue. Reload the portal.')
      const item = batch.items.find(item => item.id === request.caseId)
      start = batch.windowStart; end = batch.windowEnd
      investigation = { ...item, asOf: batch.asOf, threshold: queue.ensemble.threshold,
        models: queue.models.map(({ id, version, scoreMeaning }) => ({ id, version, scoreMeaning })),
        demo: queue.models.some(model => model.scoreMeaning === 'demo priority') }
    }
    const from = typeof start === 'string' ? Date.parse(start) : NaN
    const to = typeof end === 'string' ? Date.parse(end) : NaN
    if (!Number.isFinite(from) || !Number.isFinite(to) || from >= to || from % DAY || to % DAY || to - from > 90 * DAY) throw new HttpError(400, 'Choose a range of up to 90 days with UTC midnight boundaries (end exclusive).')
    const catalog = await read('presence/catalog.json')
    const days = catalog.days.filter(day => day.date >= iso(from).slice(0, 10) && day.date <= iso(to - 1).slice(0, 10))
    let vessel = null
    const observations = []
    const covered = new Set(), empty = new Set()
    // Read sequentially to bound memory, even for large presence days.
    for (const day of days) {
      for (const hour of day.coveredHours) {
        const ts = Date.parse(day.date) + hour * HOUR
        if (ts >= from && ts < to) { covered.add(ts); if (day.hourlyCounts[hour] === 0) empty.add(ts) }
      }
      const summary = await read(`presence/${day.vesselsUrl}`)
      const identity = summary.vessels.find(value => value.id === request.vesselId)
      if (identity && (!vessel || identity.metadataRank > vessel.metadataRank)) vessel = identity
      if (identity) {
        const data = await read(`presence/${day.observationsUrl}`)
        observations.push(...data.observations.filter(row => row.vesselId === request.vesselId && Date.parse(row.ts) >= from && Date.parse(row.ts) < to))
      }
    }
    if (!vessel && !investigation) throw new HttpError(404, 'This ship has no imported records in the selected dates.')
    observations.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts) || a.id.localeCompare(b.id))
    const observedHours = new Set(observations.map(row => Date.parse(row.ts)))
    const sample = observations.length <= 24 ? observations : Array.from({ length: 24 }, (_, index) => observations[Math.round(index * (observations.length - 1) / 23)])
    const { metadataRank, ...identity } = vessel ?? { id: request.vesselId, name: null, mmsi: investigation.mmsi, vesselType: investigation.vesselType }
    const sources = [
      { id: 'identity', label: 'Imported vessel identity', detail: 'Source-reported profile; identity may reflect retrieval time rather than historical identity.' },
      { id: 'presence', label: 'Global Fishing Watch presence', detail: `Revision ${catalog.revision}. Hourly grid-cell centres, not raw AIS fixes. ${observations.length} records in the selected window.` },
      ...(investigation ? [{ id: 'queue', label: 'Investigation queue', detail: `Scored ${investigation.asOf}. ${investigation.demo ? 'Demo priority, not a validated risk measure.' : 'Inspection priority, not a probability of wrongdoing.'}` }] : []),
      ...(request.notes.trim() ? [{ id: 'notes', label: 'Analyst-provided context', detail: 'User-supplied notes; not independently verified.' }] : []),
    ]
    return {
      vessel: { ...identity, observationCount: observations.length, firstObservedAt: observations[0]?.ts ?? null, lastObservedAt: observations.at(-1)?.ts ?? null },
      window: { start: iso(from), end: iso(to), endExclusive: true },
      presence: { source: catalog.source, revision: catalog.revision, positionSemantics: catalog.positionSemantics,
        totalHours: (to - from) / HOUR, importedHours: covered.size, unimportedHours: (to - from) / HOUR - covered.size,
        coveredEmptyHours: empty.size, vesselObservedHours: observedHours.size,
        observationCount: observations.length, sampleCount: sample.length, sampleMethod: 'Evenly spaced records including first and last; not a complete track.', sample },
      investigation, analystNotes: request.notes, sources,
    }
  }
}
