import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { land } from '../data/land'
import type { Observation } from '../presence/types'
import './MapPanel.css'

const empty = { type: 'FeatureCollection', features: [] }
interface MapPanelProps {
  positions: Observation[]
  trail: any
  history: Observation[]
  selectedId: string | null
  initialBounds: [number, number, number, number] | null
  onSelect: (id: string) => void
  status: string
}

export function MapPanel(props: MapPanelProps) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const latest = useRef(props)
  const fitDone = useRef(false)
  const [ready, setReady] = useState(false)
  const [mapError, setMapError] = useState('')
  latest.current = props
  useEffect(() => {
    if (!element.current) return
    let instance: any
    try {
      instance = new maplibregl.Map({ container: element.current, style: { version: 8, sources: {}, layers: [{ id: 'ocean', type: 'background', paint: { 'background-color': '#0c0a09' } }] }, center: [12, 15], zoom: 1.25, minZoom: 0.6, maxZoom: 15, renderWorldCopies: true })
    } catch { setMapError('The map needs WebGL. Vessel search and playback are still available.'); return }
    map.current = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')
    instance.on('load', () => {
      instance.addSource('land', { type: 'geojson', data: land })
      instance.addLayer({ id: 'land-fill', type: 'fill', source: 'land', paint: { 'fill-color': '#292524' } })
      instance.addLayer({ id: 'coastlines', type: 'line', source: 'land', paint: { 'line-color': '#78716c', 'line-width': 0.8 } })
      for (const source of ['presence-trail', 'presence-history', 'presence']) instance.addSource(source, { type: 'geojson', data: empty })
      instance.addLayer({ id: 'presence-trail', type: 'line', source: 'presence-trail', paint: { 'line-color': '#a7f3c0', 'line-width': 2, 'line-opacity': 0.75 } })
      instance.addLayer({ id: 'presence-history', type: 'circle', source: 'presence-history', paint: { 'circle-radius': 3, 'circle-color': '#a7f3c0', 'circle-opacity': 0.55, 'circle-stroke-width': 1, 'circle-stroke-color': '#0c0a09' } })
      instance.addLayer({ id: 'presence', type: 'circle', source: 'presence', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 3, 7, 5], 'circle-color': '#3ebd78', 'circle-opacity': 0.9, 'circle-stroke-color': '#102a1b', 'circle-stroke-width': 0.7 } })
      instance.addLayer({ id: 'presence-selected', type: 'circle', source: 'presence', filter: ['==', ['get', 'vesselId'], ''], paint: { 'circle-radius': 7, 'circle-color': '#d9ffe5', 'circle-stroke-color': '#3ebd78', 'circle-stroke-width': 3 } })
      instance.on('click', 'presence', (event: any) => { const id = event.features?.[0]?.properties?.vesselId; if (id) latest.current.onSelect(id) })
      instance.on('mouseenter', 'presence', () => { instance.getCanvas().style.cursor = 'pointer' })
      instance.on('mouseleave', 'presence', () => { instance.getCanvas().style.cursor = '' })
      setReady(true)
    })
    instance.on('error', () => setMapError('The map could not finish rendering. Reload the page to retry.'))
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(element.current)
    return () => { observer.disconnect(); instance.remove(); map.current = null; fitDone.current = false; setReady(false) }
  }, [])
  useEffect(() => {
    if (!ready || !map.current) return
    const toGeoJSON = (rows: Observation[]) => ({ type: 'FeatureCollection', features: rows.map(row => ({ type: 'Feature', properties: { vesselId: row.vesselId, observationId: row.id }, geometry: { type: 'Point', coordinates: [row.lon, row.lat] } })) })
    map.current.getSource('presence').setData(toGeoJSON(props.positions))
    map.current.getSource('presence-trail').setData(props.trail)
    map.current.getSource('presence-history').setData(toGeoJSON(props.history))
    map.current.setFilter('presence-selected', ['==', ['get', 'vesselId'], props.selectedId ?? ''])
  }, [ready, props.positions, props.trail, props.history, props.selectedId])
  useEffect(() => {
    if (!ready || !props.initialBounds || fitDone.current) return
    const [west, south, east, north] = props.initialBounds
    map.current.fitBounds([[west, Math.max(-85, south)], [east, Math.min(85, north)]], { padding: 55, maxZoom: 7, duration: 0 })
    fitDone.current = true
  }, [ready, props.initialBounds])
  return <section className="presence-map" aria-label="Vessel presence map">
    <div ref={element} className="world-map" role="img" aria-label={`${props.positions.length.toLocaleString()} recorded vessel positions. Use the vessel list to select a vessel with the keyboard.`} />
    <div className="map-key"><span><i /> Recorded positions</span><span className="map-key-detail">Global Fishing Watch · Hourly grid centers</span></div>
    {(props.status || mapError) && <div className="map-message" role="status">{mapError || props.status}</div>}
  </section>
}
