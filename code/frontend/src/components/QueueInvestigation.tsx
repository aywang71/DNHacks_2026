import { useEffect, useRef, useState } from 'react'
import { createPresenceProvider } from '../presence/provider.mjs'
import type { PresenceVessel } from '../presence/types'
import type { QueueBatch, QueueItem } from './ModelQueue'
import { ShipAssistant } from './ShipAssistant'

const provider = createPresenceProvider(`${import.meta.env.BASE_URL}data/presence/`)
const date = (value: string) => new Date(value).toLocaleString('en-GB', { timeZone: 'UTC' }) + ' UTC'

export function QueueInvestigation({ item, batch, demo, displayName, onClose, onMap }: {
  item: QueueItem; batch: QueueBatch; demo: boolean; displayName?: string | null; onClose: () => void; onMap: () => void
}) {
  const [vessel, setVessel] = useState<PresenceVessel | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const storageKey = `investigation-notes:${item.id}`
  const [notes, setNotes] = useState(() => { try { return localStorage.getItem(storageKey) ?? '' } catch { return '' } })
  const [saveError, setSaveError] = useState('')
  const [reportReady, setReportReady] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const report = useRef<HTMLElement>(null)
  const preview = useRef<HTMLDivElement>(null)
  useEffect(() => { heading.current?.focus() }, [])
  useEffect(() => { if (reportReady) preview.current?.focus() }, [reportReady])
  useEffect(() => {
    const abort = new AbortController()
    setLoading(true); setError('')
    provider.getCatalog(abort.signal).then(catalog => provider.getVessels(catalog, { start: Date.parse(batch.windowStart), end: Date.parse(batch.windowEnd) }, abort.signal)).then(vessels => {
      if (!abort.signal.aborted) setVessel(vessels.find(value => value.id === item.vesselId) ?? null)
    }).catch(reason => { if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : 'Vessel details unavailable.') }).finally(() => { if (!abort.signal.aborted) setLoading(false) })
    return () => abort.abort()
  }, [item.vesselId, batch.windowStart, batch.windowEnd, retry])
  const name = vessel?.name || displayName || item.mmsi || item.vesselId
  const fields = [
    ['Vessel ID', item.vesselId], ['MMSI', vessel?.mmsi ?? item.mmsi], ['IMO', vessel?.imo],
    ['Flag', vessel?.flag], ['Type', vessel?.vesselType ?? item.vesselType], ['Callsign', vessel?.callsign],
    ['Observations in window', vessel?.observationCount.toLocaleString()],
    ['First observation in window', vessel && date(vessel.firstObservedAt)],
    ['Last observation in window', vessel && date(vessel.lastObservedAt)],
  ]
  const caveat = demo ? 'Demo priority score, not a validated measure of suspicious activity. Analyst inspection is required.' : 'Higher scores indicate higher inspection priority. A score alone does not establish suspicious activity.'
  function saveNotes(value: string) {
    setNotes(value)
    try { localStorage.setItem(storageKey, value); setSaveError('') } catch { setSaveError('Notes could not be saved locally. Include them in a downloaded brief before leaving.') }
  }
  function download() {
    if (!report.current) return
    const html = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Vessel evidence brief</title><style>body{font:16px/1.5 system-ui;max-width:800px;margin:40px auto;padding:20px}dt{font-weight:bold}dd{margin:0 0 10px}p{white-space:pre-wrap}</style><body>' + report.current.innerHTML + '</body></html>'
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url; link.download = `evidence-brief-${item.vesselId.replace(/[^a-zA-Z0-9_-]/g, '_')}-${batch.asOf.slice(0, 10)}.html`
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <article id="queue-investigation" className="queue-investigation" aria-label="Vessel investigation" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose() } }}>
    <header className="queue-detail-heading"><div><p className="inspection-status">To be inspected · {(item.score * 100).toFixed(1)} / 100</p><h2 ref={heading} tabIndex={-1}>{name}</h2></div><button onClick={onClose}>Close details</button></header>
    <p className="detail-caveat">{caveat}</p>
    <p className="scoring-window">Scored {date(batch.asOf)}<br />Window: {date(batch.windowStart)} – {date(batch.windowEnd)} (end exclusive)</p>
    {loading && <p className="metadata-status" role="status">Loading vessel metadata…</p>}
    {error && <p role="alert">{error} <button onClick={() => setRetry(value => value + 1)}>Retry ship data</button></p>}
    {!loading && !error && !vessel && <p>No imported vessel metadata is available for this window. Queue identity and scores are shown below.</p>}
    <h3>Vessel identity</h3>
    <dl className="identity-grid">{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? (loading ? 'Loading…' : 'Not provided')}</dd></div>)}</dl>
    <h3>Model scores</h3><ul className="model-scores">{item.modelScores.map(model => <li key={model.id}><span>{model.id} <small>v{model.version}</small></span><strong>{(model.score * 100).toFixed(1)} <small>/ 100</small></strong></li>)}</ul>
    <button className="map-action" onClick={onMap}>View ship on presence map</button>
    <label className="queue-notes">Analyst notes<textarea aria-describedby="notes-status" rows={4} maxLength={8000} value={notes} onChange={event => saveNotes(event.target.value)} placeholder="Record observations, add background context, or describe what the AI should help you investigate." /></label>
    <p id="notes-status" className={`queue-note-status ${saveError ? 'save-error' : ''}`} role="status">{saveError || (notes ? 'Saved on this device for this vessel and scoring window.' : 'Notes save automatically on this device.')}</p>
    <ShipAssistant target={{ vesselId: item.vesselId, caseId: item.id }} notes={notes} />
    <details className="data-only-brief"><summary>Export source fields without AI</summary><button disabled={loading} aria-expanded={reportReady} onClick={() => { setReportReady(true); if (reportReady) preview.current?.focus() }}>{reportReady ? 'View data-only brief' : 'Create data-only brief'}</button></details>
    {reportReady && <div ref={preview} tabIndex={-1} className="queue-report-preview"><div className="queue-report-actions"><p role="status">Evidence brief ready</p><button onClick={download}>Download document</button><button onClick={() => window.print()}>Print / Save PDF</button></div>
      <section ref={report} tabIndex={-1} className="queue-print-report" aria-label="Evidence brief">
        <h1>Vessel evidence brief</h1><h2>{name}</h2><p>To be inspected · Priority {(item.score * 100).toFixed(1)} / 100</p>
        <p>Scored: {date(batch.asOf)}<br />Window: {date(batch.windowStart)} – {date(batch.windowEnd)} (end exclusive)</p>
        <h3>Vessel data</h3><dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 'Not provided'}</dd></div>)}</dl>
        <h3>Model scores</h3><ul>{item.modelScores.map(model => <li key={model.id}>{model.id} v{model.version}: {(model.score * 100).toFixed(1)} / 100</li>)}</ul>
        <h3>Analyst notes</h3><p className="report-notes">{notes || 'No analyst notes recorded.'}</p>
        <p>{caveat}</p><p>Sources: exported investigation queue and Global Fishing Watch presence metadata. Missing data is marked “Not provided.”</p>
      </section>
    </div>}
  </article>
}
