import { useEffect, useState } from 'react'
import type { PresenceVessel } from '../presence/types'

interface Item { id: string; vesselId: string; mmsi: string | null; vesselType: string; score: number; modelScores: { id: string; version: string; score: number }[] }
interface Batch { asOf: string; windowEnd: string; scoredVessels: number; items: Item[] }
interface Queue { schemaVersion: number; batches: Batch[] }

export function ModelQueue({ cursor, vessels, selectedId, onSelect, onJump }: {
  cursor: number; vessels: PresenceVessel[]; selectedId: string | null
  onSelect: (id: string) => void; onJump: (date: string) => void
}) {
  const [queue, setQueue] = useState<Queue | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [limit, setLimit] = useState(30)
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    fetch(`${import.meta.env.BASE_URL}data/investigations/queue.json`, { signal: abort.signal }).then(async response => {
      if (!response.ok) throw new Error('Investigation queue unavailable. Run the backend queue export.')
      const data = await response.json() as Queue
      if (data.schemaVersion !== 1 || !Array.isArray(data.batches)) throw new Error('Unsupported queue format.')
      setQueue(data)
    }).catch(reason => { if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : 'Queue could not be loaded.') })
    return () => abort.abort()
  }, [retry])
  const batch = queue?.batches.filter(value => Date.parse(value.asOf) <= cursor && cursor < Date.parse(value.windowEnd)).at(-1)
  useEffect(() => setLimit(30), [batch?.asOf])
  const latest = queue?.batches.at(-1)
  const names = new Map(vessels.map(vessel => [vessel.id, vessel.name]))
  return <section className="model-queue" aria-label="Investigation queue">
    <header className="vessel-panel-heading"><div><h2>Investigation queue</h2><p>{batch ? `${batch.items.length} flagged of ${batch.scoredVessels} · ${batch.asOf.slice(0, 10)}` : 'Model-scored vessel windows'}</p></div></header>
    {error ? <div className="list-state" role="alert">{error}<button onClick={() => setRetry(value => value + 1)}>Retry</button></div> : !queue ? <p className="list-state" role="status">Loading scores…</p> : !batch ? <div className="list-state"><p>No scores cover this replay time.</p>{latest && <button onClick={() => onJump(latest.asOf.slice(0, 10))}>Open latest scored date</button>}</div> : <>
      <div className="queue-scroll">{batch.items.slice(0, limit).map(item => <button className={`vessel-row ${selectedId === item.vesselId ? 'selected' : ''}`} key={item.id} onClick={() => onSelect(item.vesselId)} aria-pressed={selectedId === item.vesselId}>
        <span><strong>{names.get(item.vesselId) || item.mmsi || item.vesselId}</strong><small>{item.vesselType} · {item.modelScores.map(model => `${model.id}: ${(model.score * 100).toFixed(1)}`).join(' / ')}</small></span><b className="queue-score">{(item.score * 100).toFixed(1)}</b>
      </button>)}{!batch.items.length && <p className="list-state">No vessels meet the queue threshold.</p>}</div>
      {batch.items.length > limit && <button className="show-more" onClick={() => setLimit(value => value + 30)}>Show 30 more</button>}
    </>}
  </section>
}
