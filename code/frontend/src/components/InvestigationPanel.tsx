import { lazy, Suspense, useEffect, useId, useMemo, useState } from 'react'
import type { CaseRecord, CaseStatus, EvidenceTier, RiskEvent, RiskLabel, RiskLevel } from '../types'
import { DEFAULT_WEIGHTS, SCORE_COMPONENTS, calculateAnalystScore, scoresEqual, type AnalystWeights, type ScoreKey } from '../data/gappairScore'
import { ShipSuspicionPanel } from './ShipSuspicionPanel'
import './InvestigationPanel.css'

const GapPairMap = lazy(() => import('./MapPanel').then((module) => ({ default: module.MapPanel })))

export type RiskFilter = RiskLevel | 'all'
type InvestigationSurface = 'pairs' | 'ships'

export interface InvestigationPanelProps {
  events: RiskEvent[]
  selected: RiskEvent
  onSelect: (id: string) => void
  caseRecord: CaseRecord
  onOpenCase: () => void
  onSetNotes: (notes: string) => void
  watching: boolean
  onWatch: () => void
  isOpen: boolean
  onClose: () => void
  filter: RiskFilter
  onFilter: (filter: RiskFilter) => void
}

const filterLabels: { value: RiskFilter; label: string }[] = [
  { value: 'all', label: 'All candidates' },
  { value: 'high', label: 'High' },
  { value: 'review', label: 'Review' },
  { value: 'watch', label: 'Watch' },
]

const labelCopy: Record<RiskLabel, string> = {
  investigate: 'Investigate',
  'identity-twin': 'Identity twin',
  'coordinated-fleet-pattern': 'Coordinated fleet pattern',
  'likely-coverage-or-cluster-artifact': 'Likely coverage or cluster artifact',
  'possible-port-transit': 'Possible port transit',
  'insufficient-evidence': 'Insufficient evidence',
}

const tierCopy: Record<EvidenceTier, string> = {
  imagery_corroborated: 'Imagery corroborated',
  behaviour_corroborated: 'Behaviour corroborated',
  bilateral_rendezvous_plausible: 'Bilateral rendezvous plausible',
  coordinated_fleet_activity: 'Coordinated fleet activity',
  coincidence_or_artifact: 'Coincidence or artifact',
}

const statusCopy: Record<CaseStatus, { label: string; detail: string; action: string }> = {
  'not-created': { label: 'No case', detail: 'Preserve the screening record and open a review case when ready.', action: 'Open case' },
  open: { label: 'Case open', detail: 'Analyst review is in progress. Notes are saved locally in this demo.', action: 'Mark report ready' },
  ready: { label: 'Report ready', detail: 'The evidence brief is ready for printing or handoff.', action: 'Report ready' },
}

const number = (value: number | null | undefined, digits = 2) => value === null || value === undefined ? 'Not supplied' : value.toLocaleString(undefined, { maximumFractionDigits: digits })
const signed = (value: number | null, digits = 3) => {
  if (value === null) return 'Unavailable'
  const display = Math.abs(value) < 1e-12 ? 0 : value
  return `${display > 0 ? '+' : ''}${display.toLocaleString(undefined, { maximumFractionDigits: digits })}`
}
const percentage = (value: number | null | undefined) => value === null || value === undefined ? 'Not supplied' : value.toLocaleString(undefined, { style: 'percent', maximumFractionDigits: 1 })
const time = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'
}
const bool = (value: boolean | null | undefined) => value === null || value === undefined ? 'Not supplied' : value ? 'Yes' : 'No'
const displayValue = (value: unknown) => value === null || value === undefined ? 'Not supplied' : typeof value === 'boolean' ? bool(value) : typeof value === 'number' ? number(value) : typeof value === 'string' ? value : 'Supplied'
const pairName = (event: RiskEvent) => event.vessels.map((vessel) => vessel.name || vessel.mmsi).join(' × ')

function Field({ term, value }: { term: string; value: unknown }) {
  return <div><dt>{term}</dt><dd>{displayValue(value)}</dd></div>
}

function GapPairMapFallback() {
  return <section className="presence-map risk-map" aria-label="Loading GapPair map" aria-busy="true"><div className="world-map" /><div className="map-message" role="status">Loading reachable-set geometry…</div></section>
}

export function InvestigationPanel({
  events, selected, onSelect, caseRecord, onOpenCase, onSetNotes, watching, onWatch, isOpen, onClose, filter, onFilter,
}: InvestigationPanelProps) {
  const notesId = useId()
  const tabsId = useId()
  const [surface, setSurface] = useState<InvestigationSurface>('pairs')
  const [activeTab, setActiveTab] = useState<'evidence' | 'timeline'>('evidence')
  const [notice, setNotice] = useState('')
  const [weights, setWeights] = useState<AnalystWeights>(DEFAULT_WEIGHTS)
  const [queueLimit, setQueueLimit] = useState(80)
  const isCustomWeights = !scoresEqual(weights, DEFAULT_WEIGHTS)
  const caseInfo = statusCopy[caseRecord.status]
  const selectedScore = useMemo(() => calculateAnalystScore(selected.scores, weights, selected), [selected, weights])
  const maxContribution = Math.max(0.001, ...selectedScore.components.map((component) => Math.abs(component.contribution ?? 0)))

  const rankedEvents = useMemo(() => events.map((event) => ({ event, score: calculateAnalystScore(event.scores, weights, event) }))
    .sort((left, right) => (right.score.priority ?? -Infinity) - (left.score.priority ?? -Infinity) || right.event.priority - left.event.priority || left.event.id.localeCompare(right.event.id)), [events, weights])
  const filteredEvents = useMemo(() => filter === 'all' ? rankedEvents : rankedEvents.filter(({ event }) => event.riskLevel === filter), [filter, rankedEvents])
  const selectedRank = rankedEvents.findIndex(({ event }) => event.id === selected.id) + 1

  useEffect(() => { setNotice(''); setActiveTab('evidence') }, [selected.id])
  useEffect(() => { setQueueLimit(80) }, [filter])

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, tab: 'evidence' | 'timeline') => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    setActiveTab(tab === 'evidence' ? 'timeline' : 'evidence')
  }

  const updateWeight = (key: ScoreKey, value: number) => setWeights((current) => ({ ...current, [key]: value }))
  const printReport = () => { setNotice('Print dialog opened for the screening brief.'); window.print() }

  return <section className={`investigation-shell ${isOpen ? 'is-open' : 'is-collapsed'}`} aria-label="GapPair investigation">
    <nav className="analysis-surface-switch" aria-label="Analytical surface">
      <button aria-pressed={surface === 'pairs'} onClick={() => setSurface('pairs')}><span>GapPair candidates</span><small>Paired AIS-gap heuristics</small></button>
      <button aria-pressed={surface === 'ships'} onClick={() => setSurface('ships')}><span>Ship-suspicion model</span><small>Independent per-vessel score</small></button>
    </nav>
    {surface === 'ships' ? <ShipSuspicionPanel /> : <div className="gap-pair-workspace">
      <aside className="risk-queue" aria-label="GapPair candidate queue">
        <div className="queue-heading">
          <p className="eyebrow">GapPair queue</p>
          <h2>Paired gaps requiring judgment</h2>
          <span>{filteredEvents.length.toLocaleString()} shown · ranked live</span>
        </div>
        <div className="risk-filters" aria-label="Filter pipeline risk labels">
          {filterLabels.map((item) => <button key={item.value} aria-pressed={filter === item.value} className={filter === item.value ? 'is-active' : ''} onClick={() => onFilter(item.value)}>{item.label}</button>)}
        </div>
        <p className="queue-method-note">Pipeline labels stay fixed. Sliders only change this analyst view’s local ranking.</p>
        <div className="queue-list">
          {filteredEvents.slice(0, queueLimit).map(({ event, score }, index) => <button className={`queue-item ${selected.id === event.id ? 'is-selected' : ''}`} key={event.id} onClick={() => onSelect(event.id)}>
            <span className={`risk-dot risk-${event.riskLevel}`} aria-hidden="true" />
            <span className="queue-item-main"><strong>{pairName(event)}</strong><small>#{index + 1} · {labelCopy[event.label]} · {tierCopy[event.evidenceTier]}</small></span>
            <span className="risk-score"><b>{score.priority === null ? '—' : (score.priority * 100).toFixed(0)}</b><small>live</small></span>
          </button>)}
          {!filteredEvents.length && <p className="empty-queue">No candidates match this pipeline risk label.</p>}
        </div>
        {filteredEvents.length > queueLimit && <button className="queue-more" onClick={() => setQueueLimit((value) => value + 80)}>Show 80 more ({(filteredEvents.length - queueLimit).toLocaleString()} remaining)</button>}
      </aside>

      <article className="investigation-detail">
        <header className="vessel-header">
          <div>
            <p className="eyebrow">Paired AIS dark-period candidate</p>
            <h1>{selected.name}</h1>
            <p className="vessel-meta">{selected.vesselType} · {selected.location} · window ends {time(selected.lastSeen)}</p>
            <div className="classification-row"><span className={`risk-badge risk-${selected.riskLevel}`}>{labelCopy[selected.label]}</span><span className="evidence-tier">{tierCopy[selected.evidenceTier]}</span></div>
          </div>
          <div className="header-actions">
            <button className="close-investigation" onClick={onClose}>Close</button>
            <span className={`risk-badge risk-${selected.riskLevel}`}>{selected.riskScore} / 100 pipeline</span>
            <button className={`watch-button ${watching ? 'is-watching' : ''}`} onClick={onWatch} aria-pressed={watching}>{watching ? 'Watching' : 'Add watchlist'}</button>
          </div>
        </header>

        <p className="candidate-boundary">This is a screening candidate: two AIS gaps overlap and have a feasible joint reachable area. The meeting point and dashed paths are estimated; they do not establish a rendezvous, transfer, or crime.</p>

        <section className="score-decomposition" aria-labelledby="score-heading">
          <header className="score-heading"><div><p className="eyebrow">Live analyst weighting</p><h2 id="score-heading">Why this pair ranks here</h2><p>Adjusting a signed weight re-ranks the entire queue immediately. It does not change the exported pipeline label, evidence tier, or source record.</p></div><div className="weight-state"><strong>{isCustomWeights ? 'Custom weights' : 'Pipeline weights'}</strong><span>{isCustomWeights ? 'Local analyst view' : 'Default configuration'}</span>{isCustomWeights && <button onClick={() => setWeights(DEFAULT_WEIGHTS)}>Reset defaults</button>}</div></header>
          <div className="score-overview"><div><span>Live priority index</span><strong>{selectedScore.priority === null ? 'Unavailable' : `${(selectedScore.priority * 100).toFixed(1)} / 100`}</strong><small>Queue rank #{selectedRank} of {events.length}</small></div><div><span>Reweighted raw</span><strong>{number(selectedScore.raw, 3)}</strong><small>Pipeline raw: {number(selected.scores.raw, 3)}</small></div><div><span>Available |weight| mass</span><strong>{number(selectedScore.availableWeightMass, 2)} / {number(selectedScore.totalWeightMass, 2)}</strong><small>{selectedScore.normalizer === null ? 'No scored terms' : `normalised ÷${selectedScore.availableWeightMass.toFixed(2)}`}</small></div></div>
          <p className="score-method-note">Null terms are not scored as zero. Matching the pipeline, the signed weighted sum is divided by the absolute weight mass of only the terms available for this candidate.</p>
          <div className="score-rows" role="list" aria-label="Score component decomposition">
            {selectedScore.components.map((component) => {
              const magnitude = 49 * Math.abs(component.contribution ?? 0) / maxContribution
              return <div className={`score-row ${component.value === null ? 'is-unavailable' : ''}`} role="listitem" key={component.definition.key}>
                <div className="score-name"><strong>{component.definition.shortLabel}</strong><p>{component.reason}</p></div>
                <div className="score-value"><span>Value</span><b>{component.value === null ? 'Unavailable' : component.value.toFixed(2)}</b></div>
                <label className="weight-control"><span>Weight <b>{signed(component.weight, 2)}</b></span><input type="range" min="-0.40" max="0.40" step="0.01" value={component.weight} aria-label={`${component.definition.label} weight`} onChange={(event) => updateWeight(component.definition.key, Number(event.target.value))} /></label>
                <div className="score-contribution"><span>Contribution</span><div className="contribution-bar" aria-label={`${component.definition.shortLabel} contribution ${signed(component.contribution)}`}><i className="contribution-zero" />{component.contribution !== null && <i className={`contribution-fill ${component.contribution >= 0 ? 'positive' : 'negative'}`} style={{ width: `${magnitude}%` }} />}</div><b>{signed(component.contribution)}</b></div>
              </div>
            })}
          </div>
          {selectedScore.components.some((component) => component.value === null) && <aside className="missing-score-note"><strong>Unavailable terms are excluded</strong><ul>{selectedScore.components.filter((component) => component.value === null).map((component) => <li key={component.definition.key}>{component.definition.shortLabel}: {component.reason}</li>)}</ul></aside>}
        </section>

        <section className="candidate-map-section" aria-labelledby="geometry-heading"><header><div><p className="eyebrow">Reachability geometry</p><h2 id="geometry-heading">Observed endpoints and estimated feasible area</h2></div><span>Meeting point: inferred</span></header><Suspense fallback={<GapPairMapFallback />}><GapPairMap mode="risk" riskEvent={selected} status="" /></Suspense></section>

        <section className="candidate-facts" aria-label="Candidate method details">
          <section className="fact-card feature-card"><p className="eyebrow">Pair features</p><h2>Endpoint and feasibility checks</h2><dl><Field term="Required speed" value={selected.features.requiredSpeedKn === null ? null : `${number(selected.features.requiredSpeedKn)} kn`} /><Field term="Joint dwell" value={selected.features.jointDwellHours === null ? null : `${number(selected.features.jointDwellHours)} h`} /><Field term="p_cell" value={selected.features.pCell === null ? null : number(selected.features.pCell, 4)} /><Field term="Overlap" value={`${number(selected.window.overlapHours)} h`} /><Field term="Shutoff separation" value={selected.features.startDistanceKm === null ? null : `${number(selected.features.startDistanceKm)} km / ${number(selected.features.startDeltaMin)} min`} /><Field term="Reappearance separation" value={selected.features.endDistanceKm === null ? null : `${number(selected.features.endDistanceKm)} km / ${number(selected.features.endDeltaMin)} min`} /><Field term="Component class" value={selected.features.componentClass} /><Field term="Identity twin" value={selected.features.identityTwin} /><Field term="Cross flag" value={selected.features.crossFlag} /><Field term="Sequential MMSI" value={selected.features.sequentialMmsi} /></dl></section>
          <section className="fact-card null-card"><p className="eyebrow">Within-cell permutation null</p><h2>{selected.nullModel.name}</h2><div className="lift-stat"><span>Observed lift</span><strong>{selected.nullModel.lift === null ? 'Not supplied' : `${number(selected.nullModel.lift, 1)}×`}</strong><p>{selected.nullModel.lift === null ? 'No lift was supplied.' : 'Observed pair count relative to the null mean.'}</p></div><dl><Field term="Draws" value={selected.nullModel.draws} /><Field term="Observed pairs" value={selected.nullModel.observed} /><Field term="Null mean" value={selected.nullModel.nullMean} /><Field term="Cell size" value={`${selected.nullModel.cellDeg}°`} /></dl></section>
          <section className="fact-card context-card"><p className="eyebrow">Corroboration and jurisdiction</p><h2>External context</h2><dl><Field term="VIIRS state" value={selected.corroboration.viirsState.replaceAll('_', ' ')} /><Field term="Uncorrelated detections" value={selected.corroboration.viirsUncorrelatedCount} /><Field term="Closest detection" value={selected.corroboration.viirsMinKmToMeetingPoint === null ? null : `${number(selected.corroboration.viirsMinKmToMeetingPoint)} km`} /><Field term="Zone" value={selected.jurisdiction.zone.replaceAll('_', ' ')} /><Field term="EEZ" value={selected.jurisdiction.eez} /><Field term="RFMO" value={selected.jurisdiction.rfmo} /><Field term="Shore distance" value={selected.jurisdiction.shoreDistanceKm === null ? null : `${number(selected.jurisdiction.shoreDistanceKm)} km`} /><Field term="Port distance" value={selected.jurisdiction.portDistanceKm === null ? null : `${number(selected.jurisdiction.portDistanceKm)} km`} /></dl></section>
          <section className="fact-card neighbours-card"><p className="eyebrow">Local context</p><h2>Nearby dark events</h2>{selected.neighbours.length ? <ul>{selected.neighbours.map((neighbour) => <li key={`${neighbour.mmsi}-${neighbour.deltaMin}`}><strong>{neighbour.mmsi}</strong><span>{neighbour.flag} · {number(neighbour.distanceKm)} km · {number(neighbour.deltaMin)} min</span></li>)}</ul> : <p>No nearby dark-event neighbours were exported for this candidate.</p>}</section>
        </section>

        <section className="explanation-section" aria-labelledby="provenance-heading"><p className="eyebrow">Exported provenance</p><h2 id="provenance-heading">What the pipeline says about this candidate</h2>{selected.explanations.length ? <ul>{selected.explanations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <p>No explanation text was supplied with this export.</p>}</section>

        <div className="investigation-grid">
          <section className="evidence-section" aria-label="Evidence review">
            <div className="tab-row" role="tablist" aria-label="Investigation detail">
              <button id={`${tabsId}-evidence-tab`} role="tab" aria-controls={`${tabsId}-evidence-panel`} aria-selected={activeTab === 'evidence'} tabIndex={activeTab === 'evidence' ? 0 : -1} className={activeTab === 'evidence' ? 'is-active' : ''} onClick={() => setActiveTab('evidence')} onKeyDown={(event) => handleTabKeyDown(event, 'evidence')}>Evidence ({selected.evidence.length})</button>
              <button id={`${tabsId}-timeline-tab`} role="tab" aria-controls={`${tabsId}-timeline-panel`} aria-selected={activeTab === 'timeline'} tabIndex={activeTab === 'timeline' ? 0 : -1} className={activeTab === 'timeline' ? 'is-active' : ''} onClick={() => setActiveTab('timeline')} onKeyDown={(event) => handleTabKeyDown(event, 'timeline')}>Four endpoint events</button>
            </div>
            <div className="tab-content" role="tabpanel" id={`${tabsId}-${activeTab}-panel`} aria-labelledby={`${tabsId}-${activeTab}-tab`}>
              {activeTab === 'evidence' ? <div className="evidence-list">{selected.evidence.map((evidence) => <div className="evidence-row" key={evidence.id}><span className={`confidence confidence-${evidence.confidence}`}>{evidence.confidence}</span><div><strong>{evidence.claim}</strong><p>{evidence.source} · {time(evidence.observedAt)}</p></div></div>)}<p className="uncertainty-note">Evidence records source observations and method outputs, not conclusions. An inferred corridor or meeting point remains uncertain.</p></div> : <div className="timeline-panel"><div className="timeline-heading"><h3>Observed endpoint timeline</h3><p>Four observed AIS endpoints; no movement is asserted inside the gap.</p></div><ol className="timeline-list">{selected.timeline.map((event) => <li className={event.emphasis ? 'is-emphasis' : ''} key={`${event.time}-${event.title}`}><time>{time(event.time)}</time><div><strong>{event.title}</strong><p>{event.detail}</p></div></li>)}</ol></div>}
            </div>
          </section>

          <section className="case-section" aria-label="Case workflow"><div className="case-heading"><div><p className="eyebrow">Case workspace</p><h2>{caseInfo.label}</h2></div><span className={`case-status status-${caseRecord.status}`}>{caseInfo.label}</span></div><p className="case-description">{caseInfo.detail}</p><button className="case-action" onClick={onOpenCase} disabled={caseRecord.status === 'ready'}>{caseInfo.action}</button><label htmlFor={notesId}>Analyst notes</label><textarea id={notesId} value={caseRecord.notes} onChange={(event) => onSetNotes(event.target.value)} placeholder="Record what the source supports, why it matters, and what remains unknown." rows={5} /><div className="report-actions"><button className="print-button" onClick={printReport}>Print screening brief</button>{notice && <span role="status" className="action-notice">{notice}</span>}</div></section>
        </div>
        <p className="record-attribution">{selected.attribution}</p>
      </article>
    </div>}

    <section className="print-report"><p>Maritime Risk Intelligence · GapPair screening brief</p><h1>{selected.name} — {labelCopy[selected.label]}</h1><p>{selected.imo} · Pipeline priority {number(selected.priority, 2)} · Evidence tier {tierCopy[selected.evidenceTier]}</p><h2>Observed and method evidence</h2><ul>{selected.evidence.map((item) => <li key={item.id}>{item.claim} ({item.source}, {item.observedAt}; {item.confidence} confidence)</li>)}</ul><h2>Analyst notes</h2><p>{caseRecord.notes || 'No analyst notes recorded.'}</p><p className="report-caveat">Caveat: GapPair identifies paired AIS gaps with a feasible joint reachable area. It does not establish a rendezvous, transfer, or crime. Any route or point inside the gap is estimated, not observed.</p></section>
  </section>
}
