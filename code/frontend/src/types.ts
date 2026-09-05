export type RiskLevel = 'high' | 'review' | 'watch'
export type EventKind = 'dark-period' | 'encounter' | 'loitering'
export type CaseStatus = 'not-created' | 'open' | 'ready'

export interface Evidence {
  id: string
  claim: string
  source: string
  observedAt: string
  confidence: 'high' | 'medium' | 'low'
}

export interface TimelineEvent {
  time: string
  title: string
  detail: string
  emphasis?: boolean
}

export interface Vessel {
  id: string
  name: string
  imo: string
  flag: string
  vesselType: string
  riskScore: number
  riskLevel: RiskLevel
  eventKind: EventKind
  eventLabel: string
  location: string
  lastSeen: string
  coordinates: [number, number]
  evidence: Evidence[]
  timeline: TimelineEvent[]
}

export interface CaseRecord {
  id: string
  status: CaseStatus
  notes: string
  createdAt?: string
}
