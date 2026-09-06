import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { land } from '../data/land'
import { portFeatures, ports } from '../data/ports'
import type { GeoPosition, RiskEvent } from '../types'
import type { Observation } from '../presence/types'
import './MapPanel.css'

const empty = { type: 'FeatureCollection', features: [] }
const isFinitePosition = (value: unknown): value is GeoPosition => Array.isArray(value) && value.length === 2 && value.every((item) => typeof item === 'number' && Number.isFinite(item))

export interface MapPanelProps {
  mode?: 'presence' | 'risk'
  positions?: Observation[]
  trail?: unknown
  history?: Observation[]
  selectedId?: string | null
  initialBounds?: [number, number, number, number] | null
  onSelect?: (id: string) => void
  riskEvent?: RiskEvent | null
  status: string
}

interface RiskLayers {
  observed: { type: string; features: unknown[] }
  projections: { type: string; features: unknown[] }
  meeting: { type: string; features: unknown[] }
  reachable: { type: string; features: unknown[] }
}

function splitDatelineLine(coordinates: GeoPosition[]): GeoPosition[][] {
  if (coordinates.length < 2) return []
  const segments: GeoPosition[][] = []
  let current: GeoPosition[] = [coordinates[0]]
  for (let index = 1; index < coordinates.length; index += 1) {
    const start = coordinates[index - 1]
    const end = coordinates[index]
    const difference = end[0] - start[0]
    if (Math.abs(difference) <= 180) {
      current.push(end)
      continue
    }
    const adjustedEnd = end[0] + (difference > 0 ? -360 : 360)
    const boundary = start[0] >= 0 ? 180 : -180
    const fraction = (boundary - start[0]) / (adjustedEnd - start[0])
    const latitude = start[1] + (end[1] - start[1]) * fraction
    current.push([boundary, latitude])
    if (current.length > 1) segments.push(current)
    current = [[-boundary, latitude], end]
  }
  if (current.length > 1) segments.push(current)
  return segments
}

function riskLayers(event: RiskEvent | null | undefined): RiskLayers {
  const result: RiskLayers = {
    observed: { ...empty, features: [] },
    projections: { ...empty, features: [] },
    meeting: { ...empty, features: [] },
    reachable: { ...empty, features: [] },
  }
  if (!event) return result
  const isDateline = event.track.properties.dateline === true
  for (const feature of event.track.features) {
    const { geometry, properties } = feature
    if (geometry.type === 'Polygon') {
      // The export intentionally omits dateline rings. Keep that safety rule
      // in the renderer too so an additive backend field cannot paint a world-
      // spanning inferred ellipse across the map.
      if (!isDateline) result.reachable.features.push(feature)
    } else if (geometry.type === 'LineString') {
      if (isDateline) {
        splitDatelineLine(geometry.coordinates).forEach((coordinates) => {
          result.projections.features.push({ ...feature, geometry: { type: 'LineString', coordinates } })
        })
      } else {
        result.projections.features.push(feature)
      }
    } else if (properties.observationStatus === 'observed') {
      result.observed.features.push(feature)
    } else if (properties.kind === 'meetingPoint') {
      result.meeting.features.push(feature)
    }
  }
  return result
}

function trackPositions(event: RiskEvent): GeoPosition[] {
  const dateline = event.track.properties.dateline === true
  const positions: GeoPosition[] = []
  for (const feature of event.track.features) {
    if (dateline && feature.geometry.type === 'Polygon') continue
    if (feature.geometry.type === 'Point') positions.push(feature.geometry.coordinates)
    if (feature.geometry.type === 'LineString') positions.push(...feature.geometry.coordinates)
    if (feature.geometry.type === 'Polygon') positions.push(...feature.geometry.coordinates.flat())
  }
  return positions.filter(isFinitePosition)
}

function fitRiskEvent(map: any, event: RiskEvent) {
  const positions = trackPositions(event)
  if (!positions.length) return
  const dateline = event.track.properties.dateline === true
  const anchor = positions[0][0]
  const longitudes = positions.map(([longitude]) => dateline ? anchor + ((longitude - anchor + 540) % 360) - 180 : longitude)
  const latitudes = positions.map(([, latitude]) => latitude)
  let west = Math.min(...longitudes)
  let east = Math.max(...longitudes)
  let south = Math.max(-85, Math.min(...latitudes))
  let north = Math.min(85, Math.max(...latitudes))
  if (west === east) { west -= 0.15; east += 0.15 }
  if (south === north) { south = Math.max(-85, south - 0.1); north = Math.min(85, north + 0.1) }
  map.fitBounds([[west, south], [east, north]], { padding: 54, maxZoom: 7, duration: 350 })
}

export function MapPanel(props: MapPanelProps) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const latest = useRef(props)
  const presenceFitDone = useRef(false)
  const riskFitId = useRef<string | null>(null)
  const [ready, setReady] = useState(false)
  const [mapError, setMapError] = useState('')
  const isRisk = props.mode === 'risk'
  latest.current = props

  useEffect(() => {
    if (!element.current) return
    let instance: any
    const portMarkers: any[] = []
    try {
      instance = new maplibregl.Map({ container: element.current, style: { version: 8, sources: {}, layers: [{ id: 'ocean', type: 'background', paint: { 'background-color': '#0c0a09' } }] }, center: [12, 15], zoom: 1.25, minZoom: 0.6, maxZoom: 15, renderWorldCopies: true })
    } catch {
      setMapError('The map needs WebGL. The analytical record remains available below.')
      return
    }
    map.current = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')
    instance.on('load', () => {
      instance.addSource('land', { type: 'geojson', data: land })
      instance.addLayer({ id: 'land-fill', type: 'fill', source: 'land', paint: { 'fill-color': '#292524' } })
      instance.addSource('ports', { type: 'geojson', data: portFeatures })
      instance.addLayer({ id: 'ports', type: 'circle', source: 'ports', minzoom: 2.5, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 2.5, 3.5, 6, 5.5], 'circle-color': '#d946ef', 'circle-stroke-color': '#f5d0fe', 'circle-stroke-width': 1.5 } })
      const setPortLabelVisibility = () => {
        const visible = instance.getZoom() >= 4
        portMarkers.forEach((marker) => marker.getElement().classList.toggle('is-visible', visible))
      }
      ports.forEach(([name, lon, lat]) => {
        const label = document.createElement('span')
        label.className = 'port-label'
        label.textContent = name
        label.setAttribute('aria-hidden', 'true')
        portMarkers.push(new maplibregl.Marker({ element: label, anchor: 'left', offset: [7, 0] }).setLngLat([lon, lat]).addTo(instance))
      })
      instance.on('zoom', setPortLabelVisibility)
      setPortLabelVisibility()

      for (const source of ['presence-trail', 'presence-history', 'presence', 'risk-observed', 'risk-projections', 'risk-meeting', 'risk-reachable']) {
        instance.addSource(source, { type: 'geojson', data: empty })
      }
      instance.addLayer({ id: 'presence-trail', type: 'line', source: 'presence-trail', paint: { 'line-color': '#a7f3c0', 'line-width': 2, 'line-opacity': 0.75 } })
      instance.addLayer({ id: 'presence-history', type: 'circle', source: 'presence-history', paint: { 'circle-radius': 3, 'circle-color': '#a7f3c0', 'circle-opacity': 0.55, 'circle-stroke-width': 1, 'circle-stroke-color': '#0c0a09' } })
      instance.addLayer({ id: 'presence', type: 'circle', source: 'presence', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 3, 7, 5], 'circle-color': '#3ebd78', 'circle-opacity': 0.9, 'circle-stroke-color': '#102a1b', 'circle-stroke-width': 0.7 } })
      instance.addLayer({ id: 'presence-selected', type: 'circle', source: 'presence', filter: ['==', ['get', 'vesselId'], ''], paint: { 'circle-radius': 7, 'circle-color': '#d9ffe5', 'circle-stroke-color': '#3ebd78', 'circle-stroke-width': 3 } })

      instance.addLayer({ id: 'risk-reachable-fill', type: 'fill', source: 'risk-reachable', paint: { 'fill-color': ['match', ['get', 'vessel'], 'A', '#60a5fa', 'B', '#f4b860', '#a8a29e'], 'fill-opacity': 0.13 } })
      instance.addLayer({ id: 'risk-reachable-outline', type: 'line', source: 'risk-reachable', paint: { 'line-color': ['match', ['get', 'vessel'], 'A', '#60a5fa', 'B', '#f4b860', '#a8a29e'], 'line-width': 1.3, 'line-opacity': 0.72, 'line-dasharray': [1, 2] } })
      instance.addLayer({ id: 'risk-projections', type: 'line', source: 'risk-projections', paint: { 'line-color': ['match', ['get', 'vessel'], 'A', '#78b8ff', 'B', '#ffd18a', '#a8a29e'], 'line-width': 2.2, 'line-opacity': 0.78, 'line-dasharray': [2, 2] } })
      instance.addLayer({ id: 'risk-observed', type: 'circle', source: 'risk-observed', paint: { 'circle-radius': 5.2, 'circle-color': ['match', ['get', 'vessel'], 'A', '#60a5fa', 'B', '#f4b860', '#fafaf9'], 'circle-stroke-color': '#0c0a09', 'circle-stroke-width': 1.8 } })
      instance.addLayer({ id: 'risk-meeting', type: 'circle', source: 'risk-meeting', paint: { 'circle-radius': 6.5, 'circle-color': '#57534e', 'circle-opacity': 0.8, 'circle-stroke-color': '#f4b860', 'circle-stroke-width': 2 } })

      instance.on('click', 'presence', (event: any) => {
        const id = event.features?.[0]?.properties?.vesselId
        if (id) latest.current.onSelect?.(id)
      })
      instance.on('mouseenter', 'presence', () => { instance.getCanvas().style.cursor = 'pointer' })
      instance.on('mouseleave', 'presence', () => { instance.getCanvas().style.cursor = '' })
      setReady(true)
    })
    instance.on('error', () => setMapError('The map could not finish rendering. Reload the page to retry.'))
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(element.current)
    return () => {
      observer.disconnect()
      portMarkers.forEach((marker) => marker.remove())
      instance.remove()
      map.current = null
      presenceFitDone.current = false
      riskFitId.current = null
      setReady(false)
    }
  }, [])

  useEffect(() => {
    if (!ready || !map.current) return
    const toGeoJSON = (rows: Observation[]) => ({ type: 'FeatureCollection', features: rows.map((row) => ({ type: 'Feature', properties: { vesselId: row.vesselId, observationId: row.id }, geometry: { type: 'Point', coordinates: [row.lon, row.lat] } })) })
    map.current.getSource('presence').setData(toGeoJSON(isRisk ? [] : props.positions ?? []))
    map.current.getSource('presence-trail').setData(isRisk ? empty : props.trail ?? empty)
    map.current.getSource('presence-history').setData(toGeoJSON(isRisk ? [] : props.history ?? []))
    map.current.setFilter('presence-selected', ['==', ['get', 'vesselId'], isRisk ? '' : props.selectedId ?? ''])
  }, [ready, isRisk, props.positions, props.trail, props.history, props.selectedId])

  useEffect(() => {
    if (!ready || !map.current) return
    const layers = isRisk ? riskLayers(props.riskEvent) : riskLayers(null)
    map.current.getSource('risk-observed').setData(layers.observed)
    map.current.getSource('risk-projections').setData(layers.projections)
    map.current.getSource('risk-meeting').setData(layers.meeting)
    map.current.getSource('risk-reachable').setData(layers.reachable)
  }, [ready, isRisk, props.riskEvent])

  useEffect(() => {
    if (!ready || isRisk || !props.initialBounds || presenceFitDone.current) return
    const [west, south, east, north] = props.initialBounds
    map.current.fitBounds([[west, Math.max(-85, south)], [east, Math.min(85, north)]], { padding: 55, maxZoom: 7, duration: 0 })
    presenceFitDone.current = true
  }, [ready, isRisk, props.initialBounds])

  useEffect(() => {
    if (!ready || !isRisk || !props.riskEvent || riskFitId.current === props.riskEvent.id) return
    fitRiskEvent(map.current, props.riskEvent)
    riskFitId.current = props.riskEvent.id
  }, [ready, isRisk, props.riskEvent])

  const count = props.positions?.length ?? 0
  const ariaLabel = isRisk
    ? `GapPair geometry for ${props.riskEvent?.name ?? 'the selected candidate'}. Solid points are observed AIS endpoints; dashed lines and reachable areas are estimated.`
    : `${count.toLocaleString()} recorded vessel positions. Use the vessel list to select a vessel with the keyboard.`
  return <section className={`presence-map ${isRisk ? 'risk-map' : ''}`} aria-label={isRisk ? 'GapPair reachable-set map' : 'Vessel presence map'}>
    <div ref={element} className="world-map" role="img" aria-label={ariaLabel} />
    {isRisk ? <div className="map-key risk-map-key"><span><i className="observed-key" /> Observed AIS endpoints</span><span><i className="projection-key" /> Estimated gap projection</span><span><i className="reachable-key" /> Reachable set (inferred, not a track)</span><span><i className="meeting-key" /> Estimated meeting point</span></div> : <div className="map-key"><span><i /> Recorded positions</span><span><i className="port-key" /> Major ports</span><span className="map-key-detail">Global Fishing Watch · Hourly grid centers</span></div>}
    {isRisk && <p className="risk-map-caption">The point and dashed routes are inferred from endpoint constraints. {props.riskEvent?.track.properties.dateline ? 'Dateline geometry is split and reachable-set rings are omitted to avoid a misleading world-spanning polygon.' : 'Reachable-set ellipses show feasible area, not observed movement.'}</p>}
    {(props.status || mapError) && <div className="map-message" role="status">{mapError || props.status}</div>}
  </section>
}
