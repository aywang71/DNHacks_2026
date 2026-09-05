import type { PresenceCatalog, PresenceDay, DayObservations, PresenceVessel } from '../../../backend/contracts/presence'
export type { Observation, PresenceVessel, PresenceDay, PresenceCatalog, DayObservations, DayVessels } from '../../../backend/contracts/presence'

export interface TimeRange { start: number; end: number }
export interface PresenceDataProvider {
  getCatalog(signal?: AbortSignal): Promise<PresenceCatalog>
  getDay(day: PresenceDay, signal?: AbortSignal): Promise<DayObservations>
  getVessels(catalog: PresenceCatalog, range: TimeRange, signal?: AbortSignal): Promise<PresenceVessel[]>
  prefetchDay(day: PresenceDay): void
}
