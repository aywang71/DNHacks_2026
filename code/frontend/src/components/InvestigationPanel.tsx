import { useEffect, useId, useState } from 'react'
import type { CaseRecord, CaseStatus, RiskLevel, Vessel } from '../types'
import './InvestigationPanel.css'

export type RiskFilter = RiskLevel | 'all'

export interface InvestigationPanelProps {
  vessels: Vessel[]
  selected: Vessel
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
  { value: 'all', label: 'All signals' },
  { value: 'high', label: 'High risk' },
  { value: 'review', label: 'Review' },
  { value: 'watch', label: 'Watch' },
]

const statusCopy: Record<CaseStatus, { label: string; detail: string; action: string }> = {
  'not-created': { label: 'No case', detail: 'Preserve the evidence and open a review case when ready.', action: 'Open case' },
  open: { label: 'Case open', detail: 'Analyst review is in progress. Notes are saved locally in this demo.', action: 'Mark report ready' },
  ready: { label: 'Report ready', detail: 'The evidence brief is ready for printing or handoff.', action: 'Report ready' },
}

export function InvestigationPanel({
  vessels, selected, onSelect, caseRecord, onOpenCase, onSetNotes, watching, onWatch, isOpen, onClose, filter, onFilter,
}: InvestigationPanelProps) {
  const notesId = useId()
  const [activeTab, setActiveTab] = useState<'evidence' | 'timeline'>('evidence')
  const [notice, setNotice] = useState('')
  const visibleVessels = filter === 'all' ? vessels : vessels.filter((vessel) => vessel.riskLevel === filter)
  const caseInfo = statusCopy[caseRecord.status]

  useEffect(() => { setNotice('') }, [selected.id])

  const printReport = () => {
    setNotice('Print dialog opened for the evidence brief.')
    window.print()
  }

  return (
    <section className={`investigation-shell ${isOpen ? 'is-open' : 'is-collapsed'}`} aria-label="Risk investigation">
      <aside className="risk-queue" aria-label="Risk queue">
        <div className="queue-heading">
          <p className="eyebrow">Analyst queue</p>
          <h2>Signals requiring judgment</h2>
          <span>{visibleVessels.length} shown</span>
        </div>
        <div className="risk-filters" aria-label="Filter risk queue">
          {filterLabels.map((item) => (
            <button key={item.value} aria-pressed={filter === item.value} className={filter === item.value ? 'is-active' : ''} onClick={() => onFilter(item.value)}>
              {item.label}
            </button>
          ))}
        </div>
        <div className="queue-list">
          {visibleVessels.map((vessel) => (
            <button className={`queue-item ${selected.id === vessel.id ? 'is-selected' : ''}`} key={vessel.id} onClick={() => onSelect(vessel.id)}>
              <span className={`risk-dot risk-${vessel.riskLevel}`} aria-hidden="true" />
              <span className="queue-item-main"><strong>{vessel.name}</strong><small>{vessel.eventLabel} · {vessel.lastSeen}</small></span>
              <span className="risk-score">{vessel.riskScore}</span>
            </button>
          ))}
          {!visibleVessels.length && <p className="empty-queue">No signals match this filter.</p>}
        </div>
      </aside>

      <article className="investigation-detail">
        <header className="vessel-header">
          <div>
            <p className="eyebrow">Vessel investigation</p>
            <h1>{selected.name}</h1>
            <p className="vessel-meta">{selected.imo} · {selected.flag} · {selected.vesselType}</p>
          </div>
          <div className="header-actions">
            <button className="close-investigation" onClick={onClose} aria-label="Close vessel investigation">Close</button>
            <span className={`risk-badge risk-${selected.riskLevel}`}>{selected.riskScore} / 100</span>
            <button className={`watch-button ${watching ? 'is-watching' : ''}`} onClick={onWatch} aria-pressed={watching}>
              {watching ? 'Watching' : 'Add watchlist'}
            </button>
          </div>
        </header>

        <div className="investigation-grid">
          <section className="evidence-section" aria-label="Evidence review">
            <div className="tab-row" role="tablist" aria-label="Investigation detail">
              <button role="tab" aria-selected={activeTab === 'evidence'} className={activeTab === 'evidence' ? 'is-active' : ''} onClick={() => setActiveTab('evidence')}>Evidence ({selected.evidence.length})</button>
              <button role="tab" aria-selected={activeTab === 'timeline'} className={activeTab === 'timeline' ? 'is-active' : ''} onClick={() => setActiveTab('timeline')}>Replay timeline</button>
            </div>
            <div className="tab-content" role="tabpanel">
              {activeTab === 'evidence' ? <div className="evidence-list">
                {selected.evidence.map((evidence) => <div className="evidence-row" key={evidence.id}>
                  <span className={`confidence confidence-${evidence.confidence}`}>{evidence.confidence}</span>
                  <div><strong>{evidence.claim}</strong><p>{evidence.source} · {evidence.observedAt}</p></div>
                </div>)}
                <p className="uncertainty-note">Evidence records observations, not conclusions. The route across the AIS gap is an estimated corridor and remains uncertain.</p>
              </div> : <div className="timeline-panel"><div className="timeline-heading"><h3>Replay timeline</h3><p>Observed positions and signal events</p></div><ol className="timeline-list">
                {selected.timeline.map((event) => <li className={event.emphasis ? 'is-emphasis' : ''} key={`${event.time}-${event.title}`}><time>{event.time}</time><div><strong>{event.title}</strong><p>{event.detail}</p></div></li>)}
              </ol></div>}
            </div>
          </section>

          <section className="case-section" aria-label="Case workflow">
            <div className="case-heading"><div><p className="eyebrow">Case workspace</p><h2>{caseInfo.label}</h2></div><span className={`case-status status-${caseRecord.status}`}>{caseInfo.label}</span></div>
            <p className="case-description">{caseInfo.detail}</p>
            <button className="case-action" onClick={onOpenCase} disabled={caseRecord.status === 'ready'}>{caseInfo.action}</button>
            <label htmlFor={notesId}>Analyst notes</label>
            <textarea id={notesId} value={caseRecord.notes} onChange={(event) => onSetNotes(event.target.value)} placeholder="Record what you observed, why it matters, and what remains unknown." rows={5} />
            <div className="report-actions">
              <button className="print-button" onClick={printReport}>Print evidence brief</button>
              {notice && <span role="status" className="action-notice">{notice}</span>}
            </div>
          </section>
        </div>
      </article>

      <section className="print-report">
        <p>Maritime Risk Intelligence · Evidence brief</p>
        <h1>{selected.name} — {selected.eventLabel}</h1>
        <p>{selected.imo} · Risk score {selected.riskScore}/100 · Generated from curated replay data</p>
        <h2>Observed evidence</h2>
        <ul>{selected.evidence.map((item) => <li key={item.id}>{item.claim} ({item.source}, {item.observedAt}; {item.confidence} confidence)</li>)}</ul>
        <h2>Analyst notes</h2><p>{caseRecord.notes || 'No analyst notes recorded.'}</p>
        <p className="report-caveat">Caveat: AIS absence does not establish vessel activity. Any corridor shown during the gap is an estimate, not an observation.</p>
      </section>
    </section>
  )
}
