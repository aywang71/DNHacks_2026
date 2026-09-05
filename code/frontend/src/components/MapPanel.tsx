import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { land } from '../data/land'
import './MapPanel.css'

const emptyMapStyle = {
  version: 8,
  sources: {},
  layers: [{ id: 'ocean', type: 'background', paint: { 'background-color': '#0c0a09' } }],
} as const

export function MapPanel() {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)

  useEffect(() => {
    if (!element.current || map.current) return
    const instance = new maplibregl.Map({
      container: element.current,
      style: emptyMapStyle,
      center: [12, 15],
      zoom: 1.25,
      minZoom: 1,
    })
    map.current = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')
    instance.on('load', () => {
      instance.addSource('land', { type: 'geojson', data: land })
      instance.addLayer({ id: 'land-fill', type: 'fill', source: 'land', paint: { 'fill-color': '#292524', 'fill-opacity': 1 } })
      instance.addLayer({ id: 'coastlines', type: 'line', source: 'land', paint: { 'line-color': '#78716c', 'line-width': 1.1, 'line-opacity': 1 } })
    })
    return () => { instance.remove(); map.current = null }
  }, [])

  return <section className="replay-map" aria-label="Empty global map">
    <div ref={element} className="world-map" aria-hidden="true" />
    <div className="replay-map__grid" aria-hidden="true" />
    <header className="replay-map__header"><div><p className="replay-map__kicker">Map workspace</p><h1>Global map</h1><p className="replay-map__subtitle">No vessel data is currently displayed</p></div></header>
  </section>
}
