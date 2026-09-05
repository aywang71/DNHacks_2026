import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Vessel } from '../types'
import './MapPanel.css'

type Props = { vessels: Vessel[]; selected: Vessel; onSelectVessel: (id: string) => void }

const featureCollection = (vessels: Vessel[]) => ({
  type: 'FeatureCollection' as const,
  features: vessels.map(vessel => ({ type: 'Feature' as const, properties: { id: vessel.id, name: vessel.name, risk: vessel.riskLevel, score: vessel.riskScore }, geometry: { type: 'Point' as const, coordinates: vessel.coordinates } })),
})

export function MapPanel({ vessels, selected, onSelectVessel }: Props) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!element.current || map.current) return
    const instance = new maplibregl.Map({ container: element.current, style: 'https://demotiles.maplibre.org/style.json', center: [12, 15], zoom: 1.25, minZoom: 1 })
    map.current = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')
    instance.on('error', () => setFailed(true))
    instance.on('load', () => {
      instance.addSource('vessels', { type: 'geojson', data: featureCollection(vessels) })
      instance.addLayer({ id: 'vessel-halo', type: 'circle', source: 'vessels', paint: { 'circle-radius': ['interpolate', ['linear'], ['get', 'score'], 60, 12, 85, 18], 'circle-color': ['match', ['get', 'risk'], 'high', '#ff7b76', 'review', '#ffc36b', '#82e6df'], 'circle-opacity': .16 } })
      instance.addLayer({ id: 'vessel-points', type: 'circle', source: 'vessels', paint: { 'circle-radius': 6, 'circle-color': ['match', ['get', 'risk'], 'high', '#ff7b76', 'review', '#ffc36b', '#82e6df'], 'circle-stroke-width': 2, 'circle-stroke-color': '#e9ffff' } })
      instance.addLayer({ id: 'vessel-labels', type: 'symbol', source: 'vessels', layout: { 'text-field': ['get', 'name'], 'text-font': ['Open Sans Bold'], 'text-size': 12, 'text-offset': [0, 1.25], 'text-anchor': 'top' }, paint: { 'text-color': '#dff8f7', 'text-halo-color': '#061525', 'text-halo-width': 2 } })
      const pick = (event: { features?: Array<{ properties?: { id?: string } }> }) => { const id = event.features?.[0]?.properties?.id; if (id) onSelectVessel(id) }
      instance.on('click', 'vessel-points', pick)
      instance.on('mouseenter', 'vessel-points', () => { instance.getCanvas().style.cursor = 'pointer' })
      instance.on('mouseleave', 'vessel-points', () => { instance.getCanvas().style.cursor = '' })
    })
    return () => { instance.remove(); map.current = null }
  }, [onSelectVessel, vessels])

  useEffect(() => {
    const source = map.current?.getSource('vessels') as any
    source?.setData(featureCollection(vessels))
    map.current?.easeTo({ center: selected.coordinates, zoom: Math.max(map.current.getZoom(), 3), duration: 650 })
  }, [selected, vessels])

  return <section className="replay-map" aria-label="Interactive global vessel map">
    <div ref={element} className="world-map" aria-hidden="true" />
    <header className="replay-map__header"><div><p className="replay-map__kicker">Live vessel positions</p><h1>Global risk map</h1><p className="replay-map__subtitle">Select a plotted vessel to open its investigation</p></div></header>
    <div className="world-map__legend"><strong>Vessel signals</strong><span><i className="legend-hotspot high" /> High risk</span><span><i className="legend-hotspot review" /> Needs review</span><span><i className="legend-hotspot" /> Watch</span></div>
    {failed && <div className="map-fallback" role="status">Map tiles are unavailable. Vessel coordinates are still available in the investigation queue.</div>}
  </section>
}
