/**
 * Static GapPair export contract.
 *
 * The backend validates these fields in `pipeline/export.py:validate_record`.
 * Index signatures are deliberate: the export can gain additive fields without
 * making an older frontend discard them at the network boundary.
 */
export type RiskLevel = 'high' | 'review' | 'watch'
export type RiskLabel =
  | 'insufficient-evidence'
  | 'identity-twin'
  | 'coordinated-fleet-pattern'
  | 'likely-coverage-or-cluster-artifact'
  | 'possible-port-transit'
  | 'investigate'
export type EvidenceTier =
  | 'imagery_corroborated'
  | 'behaviour_corroborated'
  | 'bilateral_rendezvous_plausible'
  | 'coordinated_fleet_activity'
  | 'coincidence_or_artifact'
export type CorroborationState =
  | 'no_coverage'
  | 'clear_no_detection'
  | 'correlated_only'
  | 'uncorrelated_detection'
export type EvidenceConfidence = 'high' | 'medium' | 'low'
export type GeoPosition = [number, number]
export type ScoreComponentKey = 'geom' | 'kin' | 'beh' | 'ctx' | 'cor' | 'den' | 'flt' | 'hab'

export interface RiskVessel {
  mmsi: string
  imo: string | null
  name: string | null
  flag: string
  vesselClass: string
  role: string
  identityStatus: string
  flagCard: 'none' | 'yellow' | 'red' | 'unknown'
  rfmoAuthorized: boolean | null
  iuuListed: boolean | null
  lengthM: number | null
  tonnageGt: number | null
  lengthEstimated: boolean
  tonnageEstimated: boolean
  gapsInCorpus: number | null
  pairsInQueue: number | null
  [key: string]: unknown
}

export interface Window {
  start: string
  end: string
  overlapStart: string
  overlapEnd: string
  overlapHours: number
  [key: string]: unknown
}

export interface MeetingPoint {
  coordinates: GeoPosition
  kind: 'inferred'
  method?: string
  [key: string]: unknown
}

export interface Jurisdiction {
  zone: string
  eez: unknown | null
  rfmo: string | null
  eezEntryWhileDark: unknown | null
  shoreDistanceKm: number | null
  portDistanceKm: number | null
  [key: string]: unknown
}

export interface Scores {
  geom: number | null
  kin: number | null
  beh: number | null
  ctx: number | null
  cor: number | null
  den: number | null
  flt: number | null
  hab: number | null
  raw: number | null
  [key: string]: unknown
}

/** Additive S6 provenance emitted by newer exports. */
export interface ScoreProvenance {
  value: number | null
  weight: number
  inputs: Record<string, unknown>
  reason: string
  available: boolean
  [key: string]: unknown
}

export interface Features {
  startDistanceKm: number | null
  startDeltaMin: number | null
  endDistanceKm: number | null
  endDeltaMin: number | null
  durationRatio: number | null
  requiredSpeedKn: number | null
  jointDwellHours: number | null
  kinPlausibility: number | null
  pCell: number | null
  localDarkCount: number | null
  localUniqueVessels: number | null
  localSameFlagShare: number | null
  componentSize: number | null
  componentClass: string
  sequentialMmsi: boolean
  identityTwin: boolean
  crossFlag: boolean
  gapUnusualness: number | null
  knownPartners: number | null
  loiterBracket: unknown | null
  encounterBracket: unknown | null
  portAfterGapRisk: unknown | null
  possiblePortTransit: unknown | null
  [key: string]: unknown
}

export interface Corroboration {
  viirsState: CorroborationState
  viirsUncorrelatedCount: number
  viirsMinKmToMeetingPoint: number | null
  viirsDetections: unknown[]
  presenceSource: string
  [key: string]: unknown
}

export interface NullModel {
  name: string
  draws: number
  cellDeg: number
  observed: number
  nullMean: number | null
  lift: number | null
  [key: string]: unknown
}

export interface Neighbour {
  mmsi: string
  flag: string
  deltaMin: number | null
  distanceKm: number | null
  [key: string]: unknown
}

export interface Evidence {
  id: string
  claim: string
  source: string
  observedAt: string
  confidence: EvidenceConfidence
  [key: string]: unknown
}

export interface TimelineEvent {
  time: string
  title: string
  detail: string
  emphasis?: boolean
  [key: string]: unknown
}

export interface TrackFeatureProperties {
  vessel?: 'A' | 'B'
  role?: 'off' | 'on'
  observationStatus: 'observed' | 'estimated'
  kind?: 'meetingPoint' | 'reachableSet'
  confidence?: string
  lineStyle?: 'dashed'
  time?: string
  mmsi?: string
  source?: string
  [key: string]: unknown
}

export type TrackGeometry =
  | { type: 'Point'; coordinates: GeoPosition }
  | { type: 'LineString'; coordinates: GeoPosition[] }
  | { type: 'Polygon'; coordinates: GeoPosition[][] }

export interface TrackFeature {
  type: 'Feature'
  properties: TrackFeatureProperties
  geometry: TrackGeometry
  [key: string]: unknown
}

export interface TrackFeatureCollection {
  type: 'FeatureCollection'
  properties: { dateline: boolean; [key: string]: unknown }
  features: TrackFeature[]
  [key: string]: unknown
}

export interface SourceRecord {
  claim: string
  value: unknown
  source: string
  asOf: string
  [key: string]: unknown
}

export interface RiskEvent {
  id: string
  tier: 'paired-dark'
  label: RiskLabel
  evidenceTier: EvidenceTier
  priority: number
  riskScore: number
  riskLevel: RiskLevel
  eventKind: 'dark-period'
  eventLabel: string
  name: string
  imo: string
  flag: string
  vesselType: string
  location: string
  lastSeen: string
  coordinates: GeoPosition
  vessels: [RiskVessel, RiskVessel]
  window: Window
  meetingPoint: MeetingPoint
  jurisdiction: Jurisdiction
  scores: Scores
  availableScoreComponents?: ScoreComponentKey[]
  scoreProvenance?: Record<ScoreComponentKey, ScoreProvenance>
  features: Features
  corroboration: Corroboration
  nullModel: NullModel
  neighbours: Neighbour[]
  explanations: string[]
  evidence: Evidence[]
  timeline: TimelineEvent[]
  track: TrackFeatureCollection
  sources: SourceRecord[]
  attribution: string
  analystDisposition: unknown | null
  [key: string]: unknown
}

export interface ShipSuspicionFeature {
  name: string
  value: number
  contribution: number
  [key: string]: unknown
}

export interface ShipSuspicionVessel {
  mmsi: string
  name: string | null
  flag: string | null
  vesselClass: string | null
  score: number
  rank: number
  topFeatures: ShipSuspicionFeature[]
  [key: string]: unknown
}

export interface ShipSuspicionModel {
  name: string
  version: string
  trainedAt: string
  features: string[]
  metrics: Record<string, number>
  caveat: string
  [key: string]: unknown
}

export interface ShipSuspicionPayload {
  schemaVersion: 1
  generatedAt: string
  model: ShipSuspicionModel
  vessels: ShipSuspicionVessel[]
  [key: string]: unknown
}

/** Static inspection-queue contract shared by the queue and its detail view. */
export interface QueueModelScore {
  id: string
  version: string
  score: number
  [key: string]: unknown
}

export interface QueueItem {
  id: string
  vesselId: string
  mmsi: string | null
  vesselType: string
  score: number
  modelScores: QueueModelScore[]
  [key: string]: unknown
}

export interface QueueBatch {
  asOf: string
  windowStart: string
  windowEnd: string
  scoredVessels: number
  items: QueueItem[]
  [key: string]: unknown
}

export interface InvestigationQueue {
  schemaVersion: number
  batches: QueueBatch[]
  ensemble: { threshold: number; [key: string]: unknown }
  models: { id: string; scoreMeaning: string; [key: string]: unknown }[]
  [key: string]: unknown
}

export type CaseStatus = 'not-created' | 'open' | 'ready'

export interface CaseRecord {
  id: string
  status: CaseStatus
  notes: string
  createdAt?: string
}
