import { useEffect, useRef, useState } from 'react'
import { QueueInvestigation } from './QueueInvestigation'
import type { PresenceVessel } from '../presence/types'

export interface QueueItem { id: string; vesselId: string; mmsi: string | null; vesselType: string; score: number; modelScores: { id: string; version: string; score: number }[] }
export interface QueueBatch { asOf: string; windowStart: string; windowEnd: string; scoredVessels: number; items: QueueItem[] }
interface Queue { schemaVersion: number; batches: QueueBatch[]; ensemble: { threshold: number }; models: { id: string; scoreMeaning: string }[] }

export function ModelQueue({ cursor, vessels, onSelect, onJump, mode = 'cursor' }: {
  cursor: number; vessels: PresenceVessel[]; selectedId: string | null
  onSelect: (id: string) => void; onJump: (date: string) => void; mode?: 'cursor' | 'latest'
}) {
  const [openedId, setOpenedId] = useState<string | null>(null)
  const [queue, setQueue] = useState<Queue | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [limit, setLimit] = useState(30)
  const [query, setQuery] = useState('')
  const opener = useRef<HTMLButtonElement | null>(null)
  const search = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    fetch(`${import.meta.env.BASE_URL}data/investigations/queue.json`, { signal: abort.signal }).then(async response => {
      if (!response.ok) throw new Error('The investigation queue could not be loaded. Try again to reconnect.')
      const data = await response.json() as Queue
      if (data.schemaVersion !== 1 || !Array.isArray(data.batches)) throw new Error('This queue format is not supported. Ask your data administrator to update the export.')
      setQueue(data)
    }).catch(reason => { if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : 'Queue could not be loaded.') })
    return () => abort.abort()
  }, [retry])
  const latest = queue?.batches.at(-1)
  const batch = mode === 'latest' ? latest : queue?.batches.filter(value => Date.parse(value.asOf) <= cursor && cursor < Date.parse(value.windowEnd)).at(-1)
  useEffect(() => setLimit(30), [batch?.asOf, query])
  const names = new Map(vessels.map(vessel => [vessel.id, vessel.name]))
  const opened = batch?.items.find(item => item.id === openedId)
  const demo = queue?.models.some(model => model.scoreMeaning === 'demo priority') ?? false
  const matching = batch?.items.filter(item => [names.get(item.vesselId), item.mmsi, item.vesselId, item.vesselType].some(value => value?.toLowerCase().includes(query.trim().toLowerCase()))) ?? []
  function closeDetails() {
    setOpenedId(null)
    requestAnimationFrame(() => {
      if (opener.current?.isConnected) opener.current.focus()
      else search.current?.focus()
    })
  }
  return <section className={`model-queue ${mode === 'latest' ? 'model-queue-full' : ''} ${opened ? 'has-investigation' : ''}`} aria-label="Investigation queue">
    <header className="queue-heading"><div><h1>Investigation queue</h1><p>Review prioritized vessels and record your findings.</p></div>{batch && <div className="queue-summary"><strong>{batch.items.length.toLocaleString()} <span>to inspect</span></strong><span>of {batch.scoredVessels.toLocaleString()} scored · {batch.asOf.slice(0, 10)}</span></div>}</header>
    <p className="queue-explanation">{demo && <strong>Demo scores. </strong>}Higher scores indicate inspection priority, not evidence of suspicious activity.{queue && ` Threshold: ${(queue.ensemble.threshold * 100).toFixed(0)} / 100.`}</p>
    <div className="queue-list-pane">
      <div className="queue-filter"><label htmlFor="queue-search">Search queue</label><input ref={search} id="queue-search" type="search" placeholder="Vessel name, MMSI, ID, or type" value={query} onChange={event => setQuery(event.target.value)} /><div className="queue-columns"><span aria-live="polite">{error ? 'Unavailable' : !queue ? 'Loading…' : `${matching.length.toLocaleString()} ${query ? 'matches' : 'vessels'}`}</span><span>Priority / 100</span></div></div>
      {error ? <div className="list-state" role="alert"><h2>Queue unavailable</h2><p>{error}</p><button onClick={() => setRetry(value => value + 1)}>Retry queue</button></div> : !queue ? <div className="list-state loading-state" role="status">Loading scores…</div> : !batch ? <div className="list-state"><h2>No scoring window</h2><p>No scores cover this replay time.</p>{latest && <button onClick={() => onJump(latest.asOf.slice(0, 10))}>Open latest scored date</button>}</div> : <>
        <div className="queue-scroll">{matching.slice(0, limit).map(item => <button className={`vessel-row ${openedId === item.id ? 'selected' : ''}`} key={item.id} onClick={event => { opener.current = event.currentTarget; setOpenedId(item.id) }} aria-pressed={openedId === item.id} aria-controls={openedId === item.id ? 'queue-investigation' : undefined}>
          <span><strong>{names.get(item.vesselId) || item.mmsi || item.vesselId}</strong><small>{item.vesselType.replaceAll('_', ' ').toLowerCase()}</small></span><span className="queue-priority"><b className="queue-score">{(item.score * 100).toFixed(1)}</b><small>{openedId === item.id ? 'Selected' : 'Inspect vessel'}</small></span>
        </button>)}{!matching.length && <div className="list-state"><h2>{query ? 'No matching vessels' : 'Queue clear'}</h2><p>{query ? 'Try a vessel name, identifier, or vessel type.' : 'No vessels meet the priority threshold for this window.'}</p>{query && <button onClick={() => { setQuery(''); search.current?.focus() }}>Clear search</button>}</div>}</div>
        {matching.length > limit && <button className="show-more" onClick={() => setLimit(value => value + 30)}>Show {Math.min(30, matching.length - limit)} more <span>({(matching.length - limit).toLocaleString()} remaining)</span></button>}
      </>}
    </div>
    {opened && batch ? <QueueInvestigation key={opened.id} item={opened} displayName={names.get(opened.vesselId)} batch={batch} demo={demo} onClose={closeDetails} onMap={() => { onJump(batch.asOf.slice(0, 10)); onSelect(opened.vesselId) }} /> : <div className="queue-detail-empty"><h2>Select a vessel to investigate</h2><p>Review vessel identity and model scores, add analyst notes, then create an evidence brief.</p><span>Start with a vessel in the priority list.</span></div>}
  </section>
}
