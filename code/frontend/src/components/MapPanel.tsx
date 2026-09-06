import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { land } from '../data/land'
import { portFeatures, ports } from '../data/ports'
import { createObservationInterpolator } from '../presence/timeline.mjs'
import { formatTime } from '../presence/format'
import type { Observation, PresenceVessel } from '../presence/types'
import './MapPanel.css'

const empty = { type: 'FeatureCollection', features: [] }
interface PopupTarget { vesselId: string; observationId: string; coordinates: [number, number] }
export interface MapPanelProps {
  positions: Observation[]
  nextPositions: Observation[]
  playing: boolean
  transitionDuration: number
  onTransitionEnd: () => void
  trail: any
  history: Observation[]
  direction: any
  cursor: number
  movementEnabled: boolean
  vessels: PresenceVessel[]
  metadataReady: boolean
  selectedId: string | null
  initialBounds: [number, number, number, number] | null
  onSelect: (id: string | null) => void
  status: string
}

const vesselLabel = (vessel: PresenceVessel | undefined, observation: Observation) => vessel?.name ?? vessel?.mmsi ?? observation.vesselId
function addText(parent: HTMLElement, tag: string, value: string, className = '') {
  const element = document.createElement(tag)
  if (className) element.className = className
  element.textContent = value
  parent.append(element)
  return element
}
function popupContent(observation: Observation, vessel: PresenceVessel | undefined, metadataReady: boolean) {
  const root = document.createElement('section')
  root.className = 'vessel-popup'
  addText(root, 'p', 'Recorded vessel presence', 'vessel-popup-eyebrow')
  addText(root, 'h2', vesselLabel(vessel, observation))
  if (!metadataReady) addText(root, 'p', 'Loading vessel metadata…', 'vessel-popup-loading')
  else if (!vessel) addText(root, 'p', 'Vessel profile was not available for this imported range.', 'vessel-popup-loading')
  else {
    const summary = [vessel.flag, vessel.vesselType].filter(Boolean).join(' · ')
    if (summary) addText(root, 'p', summary, 'vessel-popup-summary')
    const fields: Array<[string, string | null]> = [['MMSI', vessel.mmsi], ['IMO', vessel.imo], ['Callsign', vessel.callsign]]
    if (fields.some(([, value]) => value)) {
      const details = document.createElement('dl')
      for (const [label, value] of fields) if (value) { addText(details, 'dt', label); addText(details, 'dd', value) }
      root.append(details)
    }
  }
  const recorded = document.createElement('p')
  recorded.className = 'vessel-popup-observation'
  recorded.append(document.createTextNode(`${formatTime(observation.ts)}\n`))
  recorded.append(document.createTextNode(`${observation.lat.toFixed(4)}°, ${observation.lon.toFixed(4)}°\n`))
  recorded.append(document.createTextNode(`${observation.gridResolution}° grid-centre observation · ${observation.presenceHours.toFixed(2)} h present`))
  root.append(recorded)
  addText(root, 'p', 'Global Fishing Watch presence data; this is not a live or exact AIS position.', 'vessel-popup-caveat')
  return root
}

export function MapPanel(props: MapPanelProps) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const popup = useRef<any>(null)
  const closingPopup = useRef(false)
  const latest = useRef(props)
  const fitDone = useRef(false)
  const playback = useRef({ positions: props.positions, nextPositions: props.nextPositions, elapsed: 0 })
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReducedMotion(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  const [popupTarget, setPopupTarget] = useState<PopupTarget | null>(null)
  const [ready, setReady] = useState(false)
  const [mapError, setMapError] = useState('')
  latest.current = props
  useEffect(() => {
    if (!element.current) return
    let instance: any
    const portMarkers: any[] = []
    try {
      instance = new maplibregl.Map({ container: element.current, style: { version: 8, sources: {}, layers: [{ id: 'ocean', type: 'background', paint: { 'background-color': '#0c0a09' } }] }, center: [12, 15], zoom: 1.25, minZoom: 0.6, maxZoom: 15, renderWorldCopies: true })
    } catch { setMapError('The map needs WebGL. Vessel search and playback are still available.'); return }
    map.current = instance
    instance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')
    instance.on('load', () => {
      instance.addSource('land', { type: 'geojson', data: land })
      instance.addLayer({ id: 'land-fill', type: 'fill', source: 'land', paint: { 'fill-color': '#292524' } })
      instance.addSource('ports', { type: 'geojson', data: portFeatures })
      instance.addLayer({ id: 'ports', type: 'circle', source: 'ports', minzoom: 2.5, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 2.5, 3.5, 6, 5.5], 'circle-color': '#d946ef', 'circle-stroke-color': '#f5d0fe', 'circle-stroke-width': 1.5 } })
      const setPortLabelVisibility = () => {
        const visible = instance.getZoom() >= 4
        portMarkers.forEach(marker => marker.getElement().classList.toggle('is-visible', visible))
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
      // Keep the base map deliberately quiet: geographic reference outlines can
      // read as latitude/longitude guides and compete with vessel movement.
      for (const source of ['presence-trail', 'presence-history', 'presence-direction', 'presence']) instance.addSource(source, { type: 'geojson', data: empty })
      instance.addLayer({ id: 'presence', type: 'circle', source: 'presence', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 3, 7, 5], 'circle-color': '#3ebd78', 'circle-opacity': ['*', 0.9, ['coalesce', ['get', 'opacity'], 1]], 'circle-stroke-color': '#102a1b', 'circle-stroke-width': 0.7 } })
      instance.addLayer({ id: 'presence-trail', type: 'line', source: 'presence-trail', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#a7f3c0', 'line-width': 2.5, 'line-opacity': ['get', 'opacity'] } })
      instance.addLayer({ id: 'presence-history', type: 'circle', source: 'presence-history', paint: { 'circle-radius': 3, 'circle-color': '#a7f3c0', 'circle-opacity': ['get', 'opacity'], 'circle-stroke-width': 1, 'circle-stroke-opacity': ['get', 'opacity'], 'circle-stroke-color': '#0c0a09' } })
      instance.addLayer({ id: 'presence-selected', type: 'circle', source: 'presence', filter: ['==', ['get', 'vesselId'], ''], paint: { 'circle-radius': 7, 'circle-color': '#d9ffe5', 'circle-opacity': ['coalesce', ['get', 'opacity'], 1], 'circle-stroke-color': '#3ebd78', 'circle-stroke-width': 3 } })
      instance.addLayer({ id: 'presence-direction', type: 'symbol', source: 'presence-direction', layout: { 'text-field': '▲', 'text-size': 17, 'text-anchor': 'bottom', 'text-rotate': ['get', 'bearing'], 'text-rotation-alignment': 'map', 'text-keep-upright': false, 'text-allow-overlap': true, 'text-ignore-placement': true }, paint: { 'text-color': '#f0fdf4', 'text-halo-color': '#102a1b', 'text-halo-width': 1.3 } })
      instance.on('click', 'presence', (event: any) => {
        const feature = event.features?.[0]
        const vesselId = feature?.properties?.vesselId, observationId = feature?.properties?.observationId
        if (!vesselId || !observationId) return
        setPopupTarget({ vesselId, observationId, coordinates: [event.lngLat.lng, event.lngLat.lat] })
        latest.current.onSelect(vesselId)
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
      closingPopup.current = true; popup.current?.remove(); popup.current = null; closingPopup.current = false
      portMarkers.forEach(marker => marker.remove())
      instance.remove(); map.current = null; fitDone.current = false; setReady(false)
    }
  }, [])
  useEffect(() => {
    if (!ready || !map.current) return
    let frame = 0
    const segment = playback.current
    if (segment.positions !== props.positions || segment.nextPositions !== props.nextPositions) {
      segment.positions = props.positions
      segment.nextPositions = props.nextPositions
      segment.elapsed = 0
    }
    const interpolate = createObservationInterpolator(props.positions, props.nextPositions)
    let previousTime = performance.now()
    const toGeoJSON = (rows: Array<Observation & { opacity?: number }>) => ({ type: 'FeatureCollection', features: rows.map(row => ({ type: 'Feature', properties: { vesselId: row.vesselId, observationId: row.id, opacity: row.opacity ?? 1 }, geometry: { type: 'Point', coordinates: [row.lon, row.lat] } })) })
    if (reducedMotion) {
      map.current.getSource('presence')?.setData(toGeoJSON(props.positions))
      if (!props.playing) return
      const timer = window.setTimeout(() => latest.current.onTransitionEnd(), props.transitionDuration)
      return () => window.clearTimeout(timer)
    }
    const draw = (now: number) => {
      // Preserve the displayed position while paused; ignore time spent in a
      // background tab so returning to playback cannot produce a sudden jump.
      if (props.playing && !document.hidden) segment.elapsed += Math.min(now - previousTime, 64)
      previousTime = now
      const progress = Math.min(segment.elapsed / props.transitionDuration, 1)
      map.current?.getSource('presence')?.setData(toGeoJSON(interpolate(progress)))
      if (props.playing) {
        if (progress < 1) frame = requestAnimationFrame(draw)
        else latest.current.onTransitionEnd()
      }
    }
    draw(previousTime)
    return () => cancelAnimationFrame(frame)
  }, [ready, props.positions, props.nextPositions, props.playing, props.transitionDuration, reducedMotion])
  useEffect(() => {
    if (!ready || !map.current) return
    const toGeoJSON = (rows: Observation[], withAgeOpacity = false) => ({ type: 'FeatureCollection', features: rows.map(row => {
      const ageHours = Math.round((props.cursor - Date.parse(row.ts)) / 3_600_000)
      return { type: 'Feature', properties: { vesselId: row.vesselId, observationId: row.id, opacity: withAgeOpacity ? Math.max(0.15, 1 - ageHours * 0.25) : 1 }, geometry: { type: 'Point', coordinates: [row.lon, row.lat] } }
    }) })
    map.current.getSource('presence-trail').setData(props.trail)
    map.current.getSource('presence-history').setData(toGeoJSON(props.history, true))
    map.current.getSource('presence-direction').setData(props.direction)
    map.current.setFilter('presence-selected', ['==', ['get', 'vesselId'], props.selectedId ?? ''])
  }, [ready, props.positions, props.trail, props.history, props.direction, props.cursor, props.selectedId])
  useEffect(() => {
    if (popupTarget && props.selectedId !== popupTarget.vesselId) setPopupTarget(null)
  }, [popupTarget, props.selectedId])
  useEffect(() => {
    const remove = () => {
      if (!popup.current) return
      closingPopup.current = true; popup.current.remove(); popup.current = null; closingPopup.current = false
    }
    if (!ready || !map.current || !popupTarget) { remove(); return }
    const observation = props.positions.find(row => row.id === popupTarget.observationId && row.vesselId === popupTarget.vesselId)
    if (!observation) { setPopupTarget(null); return }
    const vessel = props.vessels.find(entry => entry.id === observation.vesselId)
    if (!popup.current) {
      popup.current = new maplibregl.Popup({ closeButton: true, closeOnClick: false, focusAfterOpen: false, maxWidth: '290px', offset: 12 })
      popup.current.on('close', () => {
        popup.current = null
        if (!closingPopup.current) { setPopupTarget(null); latest.current.onSelect(null) }
      })
    }
    popup.current.setLngLat(popupTarget.coordinates).setDOMContent(popupContent(observation, vessel, props.metadataReady)).addTo(map.current)
  }, [ready, popupTarget, props.positions, props.vessels, props.metadataReady])
  useEffect(() => {
    if (!ready || !props.initialBounds || fitDone.current) return
    const [west, south, east, north] = props.initialBounds
    map.current.fitBounds([[west, Math.max(-85, south)], [east, Math.min(85, north)]], { padding: 55, maxZoom: 7, duration: 0 })
    fitDone.current = true
  }, [ready, props.initialBounds])
  return <section className="presence-map" aria-label="Vessel presence map">
    <div ref={element} className="world-map" role="img" aria-label={`${props.positions.length.toLocaleString()} recorded vessel positions. ${props.movementEnabled ? props.selectedId ? 'The selected vessel movement trail is visible.' : 'Movement trail is enabled; select a vessel to view it.' : 'Movement trail is off.'} Use the vessel list to select a vessel with the keyboard.`} />
    <div className="map-key"><span><i /> Recorded positions</span><span><i className="port-key" /> Major ports</span>{props.movementEnabled && <span className="movement-key">Selected movement · last 4 h</span>}<span className="map-key-detail">Global Fishing Watch · Hourly grid centers</span></div>
    {(props.status || mapError) && <div className="map-message" role="status">{mapError || props.status}</div>}
  </section>
}
