import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import type { MapPanelProps } from './components/MapPanel'
import { Timeline } from './components/Timeline'
import { VesselPanel } from './components/VesselPanel'
import { ModelQueue } from './components/ModelQueue'
import { createPresenceProvider } from './presence/provider.mjs'
import { formatTime } from './presence/format'
import { HOUR, coveredHours, createLatestRequest, currentObservations, dateRange, dayOf, earliestPositionedHour, latestPositionedHour, nextCovered, presetStart, requiredDays, trailFeatures } from './presence/timeline.mjs'
import type { Observation, PresenceCatalog, PresenceVessel } from './presence/types'
import logoLockup from './assets/logo-04-lockup.svg'

const provider = createPresenceProvider(`${import.meta.env.BASE_URL}data/presence/`)
// MapLibre is the heaviest dependency. Keep search and playback interactive while
// the map engine is fetched in its own cacheable chunk.
const MapPanel = lazy(() => import('./components/MapPanel').then(module => ({ default: module.MapPanel })))
const message = (error: unknown) => error instanceof Error ? error.message : 'Presence data could not be loaded.'
const noObservations: Observation[] = []
const noVessels: PresenceVessel[] = []
const PLAYBACK_STEP_MS = 1200

type Workspace = 'presence' | 'investigations'

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace>('presence')
  const [catalog, setCatalog] = useState<PresenceCatalog | null>(null)
  const [catalogError, setCatalogError] = useState('')
  const [catalogRetry, setCatalogRetry] = useState(0)
  const [dataRetry, setDataRetry] = useState(0)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [preset, setPreset] = useState('1')
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [bundle, setBundle] = useState<{ key: string; observations: Observation[] }>({ key: '', observations: [] })
  const [dataError, setDataError] = useState<{ key: string; message: string } | null>(null)
  const [index, setIndex] = useState<{ key: string; vessels: PresenceVessel[] }>({ key: '', vessels: [] })
  const [indexError, setIndexError] = useState<{ key: string; message: string } | null>(null)
  const dataRequest = useRef(createLatestRequest())
  const indexRequest = useRef(createLatestRequest())
  const range = useMemo(() => dateRange(startDate, endDate), [startDate, endDate])
  useEffect(() => {
    const abort = new AbortController()
    setCatalogError('')
    provider.getCatalog(abort.signal).then(value => {
      if (abort.signal.aborted) return
      const first = value.days[0]
      const latest = value.days[value.days.length - 1]
      const archiveRange = first && latest ? dateRange(first.date, latest.date) : null
      const latestCursor = archiveRange ? latestPositionedHour(value, archiveRange) : null
      const initialDate = latestCursor === null ? latest.date : dayOf(latestCursor)
      const initialRange = dateRange(initialDate, initialDate)
      const initialCursor = initialRange ? earliestPositionedHour(value, initialRange) : null
      const initialDay = value.days.find(day => day.date === initialDate) ?? latest
      const fallbackCursor = Date.parse(`${initialDate}T00:00:00Z`) + (initialDay.coveredHours[0] ?? 0) * HOUR
      setCatalog(value); setStartDate(initialDate); setEndDate(initialDate); setPreset('1')
      setCursor(initialCursor ?? fallbackCursor)
      setPlaying(true)
    }).catch(error => { if (!abort.signal.aborted) setCatalogError(message(error)) })
    return () => abort.abort()
  }, [catalogRetry])

  const available = useMemo(() => catalog && range ? coveredHours(catalog, range) : [], [catalog, range])
  const needed = useMemo(() => catalog && range ? requiredDays(cursor, range.start, catalog) : [], [catalog, cursor, range])
  const dataKey = catalog && range ? `${catalog.revision}:${needed.map(day => day.observationsUrl).join('|')}` : ''
  const indexKey = catalog && range ? `${catalog.revision}:${range.start}:${range.end}` : ''
  useEffect(() => {
    if (!catalog || !range) return
    const abort = new AbortController()
    setDataError(null)
    void dataRequest.current.run(() => Promise.all(needed.map(day => provider.getDay(day, abort.signal))), days => setBundle({ key: dataKey, observations: days.flatMap(day => day.observations) }), error => { if (!abort.signal.aborted) { setDataError({ key: dataKey, message: message(error) }); setPlaying(false) } })
    return () => { abort.abort(); dataRequest.current.invalidate() }
    // The key identifies immutable assets. Hour changes within them need no fetch.
  }, [dataKey, dataRetry])
  useEffect(() => {
    if (!catalog || !range) return
    const abort = new AbortController()
    setIndexError(null)
    void indexRequest.current.run(() => provider.getVessels(catalog, range, abort.signal), vessels => setIndex({ key: indexKey, vessels }), error => { if (!abort.signal.aborted) setIndexError({ key: indexKey, message: message(error) }) })
    return () => { abort.abort(); indexRequest.current.invalidate() }
  }, [indexKey, dataRetry])

  const isCovered = available.includes(cursor)
  const ready = Boolean(range) && bundle.key === dataKey
  const observations = ready ? bundle.observations : noObservations
  const positions = useMemo(() => currentObservations(observations, cursor), [observations, cursor])
  const nextCursor = nextCovered(available, cursor)
  const canAnimateNext = nextCursor !== null && nextCursor - cursor === HOUR
  const nextPositions = useMemo(() => canAnimateNext && nextCursor !== null ? currentObservations(observations, nextCursor) : noObservations, [observations, canAnimateNext, nextCursor])
  const vessels = range && index.key === indexKey ? index.vessels : noVessels
  const history = useMemo(() => range && selectedId ? observations.filter(row => row.vesselId === selectedId && Date.parse(row.ts) >= Math.max(range.start, cursor - 6 * HOUR) && Date.parse(row.ts) < cursor) : [], [observations, selectedId, cursor, range])
  const trail = useMemo(() => trailFeatures(observations, selectedId, cursor, range?.start ?? cursor), [observations, selectedId, cursor, range])
  const visibleIds = useMemo(() => new Set(positions.map(row => row.vesselId)), [positions])
  useEffect(() => { if (!notice) return; const timeout = window.setTimeout(() => setNotice(''), 4500); return () => window.clearTimeout(timeout) }, [notice])
  const cursorDay = dayOf(cursor)
  useEffect(() => {
    if (!playing || !catalog) return
    const next = catalog.days.find(day => day.date > cursorDay)
    if (next && range && Date.parse(`${next.date}T00:00:00Z`) < range.end) provider.prefetchDay(next)
  }, [playing, catalog, cursorDay, range])
  useEffect(() => {
    if (!playing || !ready || dataError?.key === dataKey || !range) return
    const next = nextCovered(available, cursor)
    if (next === null) {
      const first = available[0]
      if (first !== undefined && first !== cursor) setCursor(first)
      else setPlaying(false)
      return
    }
    // The map advances adjacent hours after its final animation frame.
    if (workspace === 'presence' && next - cursor === HOUR) return
    const delay = next - cursor === HOUR ? PLAYBACK_STEP_MS : 180
    const timeout = window.setTimeout(() => {
      if (next - cursor > HOUR) setNotice(`Skipped uncovered time to ${formatTime(next)}.`)
      setCursor(next)
    }, delay)
    return () => window.clearTimeout(timeout)
  }, [playing, ready, available, cursor, dataError, dataKey, range, workspace])

  function applyRange(nextStart: string, nextEnd: string, nextPreset: string) {
    setPlaying(true); setStartDate(nextStart); setEndDate(nextEnd); setPreset(nextPreset)
    const nextRange = dateRange(nextStart, nextEnd)
    if (nextRange && catalog) {
      const preferred = earliestPositionedHour(catalog, nextRange)
      setCursor(preferred ?? Math.min(Math.max(cursor, nextRange.start), nextRange.end - HOUR))
    }
  }
  function step(direction: number) {
    setPlaying(false)
    const next = nextCovered(available, cursor, direction)
    if (next !== null) { if (Math.abs(next - cursor) > HOUR) setNotice(`Skipped uncovered time to ${formatTime(next)}.`); setCursor(next) }
  }
  function scrub(value: number) { setPlaying(false); setCursor(value) }
  const currentError = dataError?.key === dataKey ? dataError.message : ''
  const mapStatus = !range ? 'Choose a valid date range.' : currentError || (!ready ? 'Loading observations…' : !isCovered ? 'No imported data for this hour.' : !positions.length ? 'No vessel positions in imported reports for this hour.' : '')
  const initialDay = catalog?.days.find(day => day.date === cursorDay) ?? catalog?.days[catalog.days.length - 1]
  function openModelResult(id: string) {
    setSelectedId(id)
    setWorkspace('presence')
  }

  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="topbar"><div className="brand"><img src={logoLockup} alt="Wake AI" /></div><nav className="workspace-nav" aria-label="Workspace"><button aria-pressed={workspace === 'presence'} onClick={() => setWorkspace('presence')}>Presence</button><button aria-pressed={workspace === 'investigations'} onClick={() => setWorkspace('investigations')}>Investigation queue</button></nav><span className="top-meta"><i className="replay-dot" /> Imported observations</span></header>
    {workspace === 'investigations' ? <main id="workspace" tabIndex={-1} className="investigation-workspace">
      <ModelQueue mode="latest" cursor={cursor} vessels={vessels} selectedId={selectedId} onSelect={openModelResult} onJump={date => { applyRange(date, date, '1'); setCursor(Date.parse(`${date}T00:00:00Z`)) }} />
    </main> : !catalog ? <main id="workspace" tabIndex={-1} className="startup" role="status"><h1>Vessel presence</h1><p>{catalogError || 'Loading the presence catalog…'}</p>{catalogError && <button onClick={() => setCatalogRetry(value => value + 1)}>Retry presence data</button>}</main> : <main id="workspace" tabIndex={-1} className="presence-workspace">
      <section className="map-workspace" aria-label="Presence replay">
        <header className="presence-toolbar">
          <div className="workspace-title"><h1>Presence map</h1><p>Explore recorded vessel positions over time.</p></div>
          <div className="date-controls">
            <div className="presets" role="group" aria-label="Time scale">{[['1', 'Day'], ['7', 'Week'], ['30', 'Month'], ['custom', 'Custom']].map(([value, name]) => <button key={value} aria-pressed={preset === value} onClick={() => { if (value === 'custom') setPreset(value); else { const end = endDate || catalog.days[catalog.days.length - 1].date; applyRange(presetStart(end, Number(value)), end, value) } }}>{name}</button>)}</div>
            <label htmlFor="start-date">From <input id="start-date" name="start-date" aria-label="Start date UTC" aria-invalid={!range} aria-describedby={!range ? 'date-range-error' : undefined} type="date" value={startDate} onChange={event => applyRange(event.target.value, endDate, 'custom')} /></label>
            <label htmlFor="end-date">Through <input id="end-date" name="end-date" aria-label="End date UTC" aria-invalid={!range} aria-describedby={!range ? 'date-range-error' : undefined} type="date" value={endDate} onChange={event => applyRange(preset === 'custom' || !event.target.value ? startDate : presetStart(event.target.value, Number(preset)), event.target.value, preset)} /></label><span className="utc-label">UTC</span>
          </div>
          {!range && <p id="date-range-error" className="date-error" role="alert">Enter both dates, with From on or before Through.</p>}
        </header>
        <div className="frame-heading"><time dateTime={new Date(cursor).toISOString()}>{formatTime(cursor)}</time><span>{!range ? 'Check date range' : currentError ? 'Data unavailable' : !ready ? 'Loading…' : `${visibleIds.size.toLocaleString()} vessels · ${positions.length.toLocaleString()} positions`}</span></div>
        <Suspense fallback={<MapLoading status={mapStatus} />}><MapPanel positions={positions} nextPositions={nextPositions} playing={playing && ready && canAnimateNext} transitionDuration={PLAYBACK_STEP_MS} onTransitionEnd={() => { if (playing && nextCursor !== null) setCursor(nextCursor) }} trail={trail} history={history} selectedId={selectedId} initialBounds={initialDay?.bounds ?? null} onSelect={setSelectedId} status={mapStatus} /></Suspense>
        {currentError && <div className="inline-error"><span>{currentError}</span><button onClick={() => setDataRetry(value => value + 1)}>Retry data</button></div>}
        <Timeline catalog={catalog} range={range} startDate={startDate} endDate={endDate} cursor={cursor} available={available} playing={playing && ready && Boolean(range) && available.length > 0 && !currentError} error={Boolean(currentError)} loading={Boolean(range) && !ready && !currentError} onPlay={() => setPlaying(value => !value)} onStep={step} onScrub={scrub} />
      </section>
      <VesselPanel vessels={vessels} selectedId={selectedId} onSelect={setSelectedId} positions={positions} visibleIds={visibleIds} ready={ready} validRange={Boolean(range)} indexReady={index.key === indexKey && Boolean(range)} indexError={indexError?.key === indexKey ? indexError.message : ''} onRetry={() => setDataRetry(value => value + 1)} onJump={scrub} rangeKey={indexKey} rangeStart={range ? new Date(range.start).toISOString() : undefined} rangeEnd={range ? new Date(range.end).toISOString() : undefined} />
    </main>}
    <div className="toast" role="status" aria-live="polite">{notice}</div>
  </div>
}

function MapLoading({ status }: Pick<MapPanelProps, 'status'>) {
  return <section className="presence-map" aria-label="Vessel presence map" aria-busy="true">
    <div className="world-map" />
    <div className="map-message" role="status">{status || 'Loading map…'}</div>
  </section>
}
