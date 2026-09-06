import { useEffect, useMemo, useState } from 'react'
import type { ShipSuspicionPayload, ShipSuspicionVessel } from '../types'

const isPayload = (value: unknown): value is ShipSuspicionPayload => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const candidate = value as Record<string, unknown>
  return candidate.schemaVersion === 1 && Array.isArray(candidate.vessels) && Boolean(candidate.model)
}

const formatMetric = (value: number) => {
  if (!Number.isFinite(value)) return 'Unavailable'
  return value >= 0 && value <= 1 ? value.toLocaleString(undefined, { style: 'percent', maximumFractionDigits: 1 }) : value.toLocaleString(undefined, { maximumFractionDigits: 3 })
}

const vesselName = (vessel: ShipSuspicionVessel) => vessel.name || vessel.mmsi

export function ShipSuspicionPanel() {
  const [payload, setPayload] = useState<ShipSuspicionPayload | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [selectedMmsi, setSelectedMmsi] = useState<string | null>(null)
  const [limit, setLimit] = useState(50)

  useEffect(() => {
    const abort = new AbortController()
    setError('')
    fetch(`${import.meta.env.BASE_URL}data/ship-suspicion.json`, { signal: abort.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('Ship-suspicion export is not available yet. Generate data/ship-suspicion.json and retry.')
        const data: unknown = await response.json()
        if (!isPayload(data)) throw new Error('Ship-suspicion export has an unsupported format.')
        if (!data.model || typeof data.model !== 'object') throw new Error('Ship-suspicion export is missing model metadata.')
        setPayload(data)
      })
      .catch((reason: unknown) => {
        if (abort.signal.aborted) return
        setError(reason instanceof Error ? reason.message : 'Ship-suspicion scores could not be loaded.')
      })
    return () => abort.abort()
  }, [retry])

  const ranked = useMemo(() => payload ? [...payload.vessels].sort((a, b) => a.rank - b.rank || b.score - a.score) : [], [payload])
  const selected = ranked.find((vessel) => vessel.mmsi === selectedMmsi) ?? ranked[0] ?? null

  useEffect(() => {
    if (selected && selectedMmsi !== selected.mmsi) setSelectedMmsi(selected.mmsi)
  }, [selected, selectedMmsi])

  return <section className="ship-suspicion" aria-label="Ship-suspicion model">
    <header className="ship-model-header">
      <div>
        <p className="eyebrow">Independent vessel model</p>
        <h1>Ship-suspicion scores</h1>
        <p>This ranks individual vessels. It is separate from the paired-gap heuristics and is not evidence of an event.</p>
      </div>
      {payload && <div className="ship-model-id"><strong>{payload.model.name}</strong><span>{payload.model.version}</span><span>trained {payload.model.trainedAt.slice(0, 10)}</span></div>}
    </header>
    {error ? <div className="ship-state" role="alert"><p>{error}</p><button onClick={() => setRetry((value) => value + 1)}>Retry ship model</button></div> : !payload ? <div className="ship-state" role="status">Loading independent vessel scores…</div> : <>
      <section className="ship-model-summary" aria-label="Ship-suspicion model notes">
        <div className="ship-caveat"><strong>Model caveat</strong><p>{payload.model.caveat || 'No caveat was supplied with this model export.'}</p></div>
        <div className="model-metrics"><strong>Reported metrics</strong><dl>{Object.entries(payload.model.metrics).map(([name, value]) => <div key={name}><dt>{name.replaceAll('_', ' ')}</dt><dd>{formatMetric(value)}</dd></div>)}</dl></div>
        <div className="model-features"><strong>Model inputs</strong><p>{payload.model.features.length ? payload.model.features.join(', ') : 'No feature list supplied.'}</p></div>
      </section>
      <div className="ship-workspace">
        <section className="ship-ranked-list" aria-label="Ranked vessel list">
          <header><h2>Ranked vessels</h2><span>{ranked.length.toLocaleString()} scored</span></header>
          <div className="ship-list-scroll">{ranked.slice(0, limit).map((vessel) => <button key={vessel.mmsi} className={`ship-row ${selected?.mmsi === vessel.mmsi ? 'is-selected' : ''}`} onClick={() => setSelectedMmsi(vessel.mmsi)} aria-pressed={selected?.mmsi === vessel.mmsi}>
            <span className="ship-rank">{vessel.rank}</span>
            <span className="ship-row-main"><strong>{vesselName(vessel)}</strong><small>{vessel.flag || 'Flag unavailable'} · {vessel.vesselClass || 'Class unavailable'}</small></span>
            <span className="ship-score">{(vessel.score * 100).toFixed(1)}</span>
          </button>)}
          {!ranked.length && <p className="ship-empty">The model export contains no vessel scores.</p>}</div>
          {ranked.length > limit && <button className="show-more" onClick={() => setLimit((value) => value + 50)}>Show 50 more ({(ranked.length - limit).toLocaleString()} remaining)</button>}
        </section>
        <section className="ship-detail" aria-label="Selected vessel model explanation">
          {selected ? <>
            <p className="eyebrow">Selected vessel</p>
            <div className="ship-detail-heading"><div><h2>{vesselName(selected)}</h2><p>{selected.mmsi} · {selected.flag || 'Flag unavailable'} · {selected.vesselClass || 'Class unavailable'}</p></div><strong>{(selected.score * 100).toFixed(1)}<small>/100 score</small></strong></div>
            <p className="ship-score-note">Model score; not a probability of wrongdoing and not a GapPair event score.</p>
            <h3>Top feature contributions</h3>
            {selected.topFeatures.length ? <ol className="ship-features">{selected.topFeatures.map((feature) => <li key={`${feature.name}-${feature.contribution}`}><div><strong>{feature.name}</strong><span>value {feature.value.toLocaleString(undefined, { maximumFractionDigits: 3 })}</span></div><b className={feature.contribution >= 0 ? 'positive' : 'negative'}>{feature.contribution >= 0 ? '+' : ''}{feature.contribution.toLocaleString(undefined, { maximumFractionDigits: 3 })}</b></li>)}</ol> : <p className="ship-empty">No feature contributions were supplied for this vessel.</p>}
          </> : <p className="ship-empty">Select a vessel to inspect its reported model contributions.</p>}
        </section>
      </div>
    </>}
  </section>
}
