import { useEffect, useMemo, useState } from 'react'
import type { Observation, PresenceVessel } from '../presence/types'
import { formatTime } from '../presence/format'

const label = (vessel: PresenceVessel) => vessel.name ?? vessel.mmsi ?? vessel.id
interface Props {
  vessels: PresenceVessel[]; selectedId: string | null; positions: Observation[]; visibleIds: Set<string>
  ready: boolean; validRange: boolean; indexReady: boolean; indexError: string; rangeKey: string
  onSelect: (id: string | null) => void; onRetry: () => void; onJump: (cursor: number) => void
}
export function VesselPanel({ vessels, selectedId, positions, visibleIds, ready, validRange, indexReady, indexError, rangeKey, onSelect, onRetry, onJump }: Props) {
  const [query, setQuery] = useState(''), [limit, setLimit] = useState(100)
  const selected = vessels.find(vessel => vessel.id === selectedId)
  const selectedPositions = positions.filter(row => row.vesselId === selectedId)
  const matching = useMemo(() => { const search = query.toLowerCase().trim(); return vessels.filter(vessel => [vessel.name, vessel.mmsi, vessel.imo, vessel.id].some(value => value?.toLowerCase().includes(search))) }, [vessels, query])
  useEffect(() => setLimit(100), [query, rangeKey])
  return <aside className="vessel-panel" aria-label="Vessels in selected range">
    <header className="vessel-panel-heading"><div><h2>Vessels</h2><p>Observed in the selected dates</p></div><span>{vessels.length.toLocaleString()}</span></header>
    <label className="vessel-search" htmlFor="vessel-search"><span className="sr-only">Search vessels</span><input id="vessel-search" name="vessel-search" type="search" aria-label="Search vessels" placeholder="Name, MMSI, IMO, or GFW ID" value={query} onChange={event => setQuery(event.target.value)} /></label>
    {selectedId && <section className="vessel-detail" aria-label="Selected vessel details"><div className="detail-title"><h2>{selected ? label(selected) : 'Selected vessel'}</h2><button aria-label="Close vessel details" onClick={() => onSelect(null)}>×</button></div>{selected ? <>
      <p className="observation-status">{!validRange ? 'Choose a valid date range.' : !ready ? 'Loading observations…' : selectedPositions.length ? `${selectedPositions.length} recorded position${selectedPositions.length === 1 ? '' : 's'} this hour` : 'No observation this hour.'}</p>
      <dl><dt>MMSI</dt><dd>{selected.mmsi ?? 'Not provided'}</dd><dt>IMO</dt><dd>{selected.imo ?? 'Not provided'}</dd><dt>Flag</dt><dd>{selected.flag ?? 'Not provided'}</dd><dt>Type</dt><dd>{selected.vesselType ?? 'Not provided'}</dd><dt>Callsign</dt><dd>{selected.callsign ?? 'Not provided'}</dd></dl>
      {selectedPositions.map(row => <p className="position-detail" key={row.id}>{row.lat.toFixed(4)}°, {row.lon.toFixed(4)}°<br /><small>{formatTime(row.ts)} · {row.gridResolution}° grid<br />{row.datasetVersion}</small></p>)}
      <button className="jump-button" onClick={() => onJump(Date.parse(selected.firstObservedAt))}>Jump to first observation</button>
      <p className="detail-source">Global Fishing Watch grid-center observations. Movement trail shows the preceding four hours; breaks indicate missing or ambiguous observations.</p><details><summary>Source identity</summary><p className="source-id">{selected.id}</p><p>First in range: {formatTime(selected.firstObservedAt)}<br />Last in range: {formatTime(selected.lastObservedAt)}</p></details>
    </> : <p>{indexReady ? 'This vessel has no observations in the selected dates.' : 'Loading vessel details…'}</p>}</section>}
    {!validRange ? <p className="list-state">Choose a valid date range.</p> : indexError ? <div className="list-state" role="alert"><p>{indexError}</p><button onClick={onRetry}>Retry vessel list</button></div> : !indexReady ? <p className="list-state" role="status">Loading vessels…</p> : <><div className="list-caption"><span>{matching.length.toLocaleString()} {query ? 'matches' : 'vessels'}</span><span>● Present this hour</span></div><div className="vessel-list">{matching.slice(0, limit).map(vessel => <button className={`vessel-row ${vessel.id === selectedId ? 'selected' : ''}`} key={vessel.id} aria-pressed={vessel.id === selectedId} onClick={() => onSelect(vessel.id)}><i className={visibleIds.has(vessel.id) ? 'is-present' : ''} aria-label={visibleIds.has(vessel.id) ? 'Present this hour' : 'Absent this hour'} /><span><strong>{label(vessel)}</strong><small>{vessel.mmsi ?? vessel.imo ?? vessel.id} · {vessel.flag ?? 'Flag unavailable'}</small></span></button>)}{!matching.length && <p className="list-state">{query ? 'No vessels match this search.' : 'No vessels observed in the selected dates.'}</p>}{matching.length > limit && <button className="show-more" onClick={() => setLimit(value => value + 100)}>Show 100 more ({(matching.length - limit).toLocaleString()} remaining)</button>}</div></>}
  </aside>
}
