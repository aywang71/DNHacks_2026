import { useEffect, useMemo, useState } from 'react'
import { dataProvider } from './data/provider'
import { vessels as fallbackVessels } from './data/mockData'
import type { CaseRecord, Vessel } from './types'
import { MapPanel } from './components/MapPanel'
import { InvestigationPanel, type RiskFilter } from './components/InvestigationPanel'

export default function App() {
  const [vessels, setVessels] = useState<Vessel[]>(fallbackVessels)
  const [selectedId, setSelectedId] = useState('ocean-star')
  const [caseRecord, setCaseRecord] = useState<CaseRecord>({ id: 'MR-260905-017', status: 'not-created', notes: '' })
  const [watchedVesselIds, setWatchedVesselIds] = useState<string[]>([])
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<RiskFilter>('all')
  useEffect(() => { dataProvider.getRiskEvents().then(setVessels).catch(() => setNotice('Offline replay data is in use.')) }, [])
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(''), 2800); return () => window.clearTimeout(timer) }, [notice])
  const selected = vessels.find(v => v.id === selectedId) ?? vessels[0]
  const matching = useMemo(() => vessels.filter(v => `${v.name} ${v.imo} ${v.location}`.toLowerCase().includes(query.toLowerCase())), [vessels, query])
  if (!selected) return null
  const selectVessel = (id: string) => { setSelectedId(id); setInspectorOpen(true) }
  const openCase = () => { setCaseRecord(current => ({ ...current, status: current.status === 'not-created' ? 'open' : 'ready', createdAt: current.createdAt ?? '05 Sep 2026, 12:08 UTC' })); setNotice(caseRecord.status === 'not-created' ? `Investigation ${caseRecord.id} is open.` : 'Evidence brief marked ready.') }
  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to investigation workspace</a>
    <header className="topbar"><div className="brand"><span className="brand-mark" aria-hidden="true" /><span>Maritime Risk Intelligence<small>Signal review workspace</small></span></div><label className="search"><span aria-hidden="true">⌕</span><span className="sr-only">Search vessel, IMO, or location</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search vessel, IMO, or location" /></label><div className="top-meta"><span className="replay-dot" /> Replay data · 05 Sep 2026 <span className="analyst">AN</span></div></header>
    <main id="workspace" className={`workspace ${inspectorOpen ? 'inspector-open' : 'inspector-closed'}`}>
      <aside className="rail" aria-label="Workspace navigation"><p>Workspace</p><button>Overview</button><button className="active" aria-current="page">Risk map</button><button>Investigations <b>12</b></button><button>Watchlists</button><button>Reports</button><section><p>Data status</p><span className="data-status">Offline-ready<br />curated replay</span></section></aside>
      <section className="map-region" aria-label="Global map"><MapPanel />{query && <div className="search-results" aria-label="Matching vessels">{matching.length ? matching.map(v => <button key={v.id} aria-current={v.id === selectedId || undefined} onClick={() => { selectVessel(v.id); setQuery('') }}>{v.name} <small>{v.imo}</small></button>) : <p role="status">No vessels match that search.</p>}</div>}</section>
      <InvestigationPanel vessels={vessels} selected={selected} onSelect={selectVessel} isOpen={inspectorOpen} onClose={() => setInspectorOpen(false)} caseRecord={caseRecord} onOpenCase={openCase} onSetNotes={notes => setCaseRecord(c => ({ ...c, notes }))} watching={watchedVesselIds.includes(selected.id)} onWatch={() => { const isWatching = watchedVesselIds.includes(selected.id); setWatchedVesselIds(ids => isWatching ? ids.filter(id => id !== selected.id) : [...ids, selected.id]); setNotice(isWatching ? 'Removed from watchlist.' : 'Added to watchlist.') }} filter={filter} onFilter={setFilter} />
    </main><div className="toast" role="status" aria-live="polite">{notice}</div>
  </div>
}
