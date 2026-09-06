import type { PresenceCatalog, TimeRange } from '../presence/types'
import { HOUR, nextCovered } from '../presence/timeline.mjs'
import { formatTime } from '../presence/format'

interface Props {
  catalog: PresenceCatalog; range: TimeRange | null; startDate: string; endDate: string; cursor: number; available: number[]
  playing: boolean; error: boolean; loading: boolean
  onPlay: () => void; onStep: (direction: number) => void; onScrub: (value: number) => void
}
export function Timeline({ catalog, range, startDate, endDate, cursor, available, playing, error, loading, onPlay, onStep, onScrub }: Props) {
  const regions = [...new Set(catalog.coverage.map(item => `${item.regionDataset} / ${item.regionId}`))].join(', ')
  return <section className="timeline" aria-label="Presence timeline">
    <div className="playback-controls"><button className="play-button" onClick={onPlay} disabled={!range || !available.length || error || loading} aria-label={playing ? 'Pause playback' : 'Play playback'}>{loading ? 'Loading…' : playing ? 'Ⅱ Pause' : '▶ Play'}</button><button onClick={() => onStep(-1)} disabled={!range || nextCovered(available, cursor, -1) === null} aria-label="Previous covered hour">←</button><button onClick={() => onStep(1)} disabled={!range || nextCovered(available, cursor) === null} aria-label="Next covered hour">→</button><span className="timeline-resolution">{loading ? 'Preparing replay' : playing ? 'Playing' : 'Paused'} · one recorded hour per step</span></div>
    <div className="scrubber">
      <div className="coverage-track" aria-hidden="true">{range && catalog.days.flatMap(day => day.coveredHours.filter(hour => { const ts = Date.parse(`${day.date}T00:00:00Z`) + hour * HOUR; return ts >= range.start && ts < range.end }).map(hour => { const ts = Date.parse(`${day.date}T00:00:00Z`) + hour * HOUR; return <span key={`${day.date}-${hour}`} className={day.hourlyCounts[hour] ? 'has-positions' : 'covered-empty'} style={{ left: `${100 * (ts - range.start) / (range.end - range.start)}%`, width: `${100 * HOUR / (range.end - range.start)}%`, opacity: day.hourlyCounts[hour] ? 0.45 + Math.min(day.hourlyCounts[hour] / 1500, 1) * 0.55 : 1 }} /> }))}</div>
      <label className="sr-only" htmlFor="presence-time">Observation time UTC</label><input id="presence-time" type="range" min={range?.start ?? 0} max={range ? range.end - HOUR : 0} step={HOUR} value={range ? cursor : 0} disabled={!range} aria-valuetext={`${formatTime(cursor)}; ${available.includes(cursor) ? 'imported coverage' : 'no imported data'}`} onChange={event => onScrub(Number(event.target.value))} />
    </div>
    <div className="timeline-labels"><span>{startDate || 'Start date'}</span><span>{endDate || 'End date'} · 23:00 UTC</span></div>
    <div className="coverage-note"><span><i /> Imported positions</span><span><i className="empty-key" /> Imported, no positions</span><span><i className="uncovered-key" /> No imported data</span></div>
    <p className="coverage-context">Coverage: {regions}. Playback skips uncovered periods.</p>
  </section>
}
