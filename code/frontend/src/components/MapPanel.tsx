import { useEffect, useMemo, useState } from 'react';
import type { Vessel } from '../types';
import './MapPanel.css';

type MapPanelProps = {
  selected: Vessel;
  onSelectVessel?: (vesselId: string) => void;
  className?: string;
};

/** Coordinates are normalized to this SVG viewbox.  The static SVG is a no-network fallback for tiles. */
const oceanStarTrack = {
  observedTrack: 'M84 386 C151 350 206 371 290 305 S374 214 438 238',
  gapCorridor: 'M438 238 C485 249 519 271 545 258 C590 238 625 249 672 207',
  reappearanceTrack: 'M672 207 C710 170 749 162 806 137',
  position: { x: 806, y: 137 },
};

const backgroundTracks = [
  'M190 108 C245 145 284 146 345 127 S455 80 521 122',
  'M590 414 C636 377 692 407 750 374',
];

export function MapPanel({ selected, onSelectVessel, className = '' }: MapPanelProps) {
  const [zoom, setZoom] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [step, setStep] = useState(3);
  const selectedTrack = useMemo(() => oceanStarTrack, []);

  useEffect(() => {
    if (!isPlaying) return undefined;
    const timer = window.setInterval(() => setStep((current) => (current >= 3 ? 0 : current + 1)), 1600);
    return () => window.clearInterval(timer);
  }, [isPlaying]);

  const reset = () => {
    setZoom(1);
    setStep(3);
    setIsPlaying(false);
  };

  const stageLabel = ['Last observed position', 'AIS unavailable — estimated corridor only', 'First reappearance', 'Evidence review'][step];

  return (
    <section className={`replay-map ${className}`} aria-label="Maritime risk map and replay">
      <p className="sr-only">Map summary: Ocean Star was last observed before an AIS gap lasting 31 hours and 18 minutes near a monitored transfer area. The amber dashed route is an estimated corridor, not observed movement. A close encounter with Ocean Pearl was observed before the gap; Ocean Star later reappeared.</p>
      <div className="replay-map__grid" aria-hidden="true" />
      <header className="replay-map__header">
        <div>
          <p className="replay-map__kicker">Guided replay</p>
          <h1>Eastern Mediterranean</h1>
          <p className="replay-map__subtitle">03–04 Sep 2026 · UTC</p>
        </div>
        <div className="replay-map__tools" aria-label="Map controls">
          <button type="button" aria-label="Zoom out" onClick={() => setZoom((value) => Math.max(0.8, value - 0.1))}>−</button>
          <button type="button" aria-label="Zoom in" onClick={() => setZoom((value) => Math.min(1.35, value + 0.1))}>+</button>
          <button type="button" className="replay-map__reset" onClick={reset}>Reset view</button>
        </div>
      </header>

      <div className="replay-map__canvas">
        <svg viewBox="0 0 900 560" role="img" aria-label={`Map replay: ${stageLabel}`} preserveAspectRatio="none">
          <g transform={`translate(450 280) scale(${zoom}) translate(-450 -280)`}>
            <path className="map-contour" d="M-20 200 C120 150 190 270 300 225 S490 140 600 220 S780 330 930 250" />
            <path className="map-contour" d="M-20 355 C150 310 230 440 370 375 S620 275 720 350 S830 400 940 355" />
            <path className="map-aoi" d="M497 220 C535 198 582 203 608 234 C623 263 598 292 555 290 C515 285 484 254 497 220Z" />
            <text className="map-label" x="530" y="310">Transfer monitoring area</text>
            {backgroundTracks.map((track) => <path className="map-track map-track--background" d={track} key={track} />)}
            <path className="map-track" d={selectedTrack.observedTrack} />
            {step >= 1 && <path className="map-gap" d={selectedTrack.gapCorridor} />}
            {step >= 2 && <path className="map-track map-track--active" d={selectedTrack.reappearanceTrack} />}
            <line className="map-encounter" x1="526" y1="264" x2="550" y2="251" />
            <circle className="map-halo" cx="545" cy="258" r="29" />
            <circle className="map-hotspot" cx="545" cy="258" r="5" />
            <g className="map-vessel" tabIndex={0} role="button" aria-label={`Select ${selected.name}`} onClick={() => onSelectVessel?.(selected.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectVessel?.(selected.id); } }}>
              <path d={`M${selectedTrack.position.x - 7} ${selectedTrack.position.y - 8} l14 8 -14 8 -5 -8z`} />
            </g>
            <circle className="map-reappearance" cx="672" cy="207" r="16" />
          </g>
        </svg>

        <button type="button" className="replay-map__event" onClick={() => onSelectVessel?.(selected.id)}>
          <span>Signal gap · 31h 18m</span>
          <small>Estimated corridor, not observed movement</small>
        </button>
      </div>

      <div className="replay-map__footer">
        <div className="replay-map__replay" aria-label="Replay controls">
          <button type="button" className="replay-map__play" aria-pressed={isPlaying} onClick={() => setIsPlaying((playing) => !playing)}>
            {isPlaying ? 'Pause replay' : 'Play replay'}
          </button>
          <input aria-label="Replay position" aria-valuetext={stageLabel} type="range" min="0" max="3" step="1" value={step} onChange={(event) => { setIsPlaying(false); setStep(Number(event.target.value)); }} />
          <output aria-live="polite">{stageLabel}</output>
        </div>
        <div className="replay-map__legend" aria-label="Map legend">
          <span><i className="legend-line" /> Observed AIS</span>
          <span><i className="legend-gap" /> Estimated gap corridor</span>
          <span><i className="legend-hotspot" /> Close encounter</span>
        </div>
      </div>
    </section>
  );
}

export default MapPanel;
