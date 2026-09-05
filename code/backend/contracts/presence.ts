/** Version 1 static presence data contract. Browser-safe types only. */
export interface Observation {
  id: string
  vesselId: string
  ts: string
  lat: number
  lon: number
  presenceHours: number
  datasetVersion: string
  gridResolution: number
}
export interface PresenceVessel {
  id: string
  name: string | null
  mmsi: string | null
  imo: string | null
  callsign: string | null
  flag: string | null
  vesselType: string | null
  firstObservedAt: string
  lastObservedAt: string
  metadataUpdatedAt: string
  metadataRank: string
  observationCount: number
}
export interface PresenceDay {
  date: string
  observationsUrl: string
  vesselsUrl: string
  bounds: [number, number, number, number] | null
  coveredHours: number[]
  hourlyCounts: number[]
  observationCount: number
  vesselCount: number
}
export interface PresenceCatalog {
  schemaVersion: 1
  revision: string
  generatedAt: string
  source: string
  positionSemantics: string
  coverage: { start: string; end: string; regionDataset: string; regionId: number; datasetVersion: string; gridResolution: number }[]
  days: PresenceDay[]
  observationCount: number
  coveredHourCount: number
}
export interface DayObservations { date: string; observations: Observation[] }
export interface DayVessels { date: string; vessels: PresenceVessel[] }
