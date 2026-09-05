import type { Observation, PresenceCatalog, PresenceDay, PresenceVessel, DayVessels, TimeRange } from './types'
export const HOUR: number
export const DAY: number
export function dayOf(timestamp: number): string
export function dateRange(startDate: string, endDate: string): TimeRange | null
export function presetStart(endDate: string, days: number): string
export function coveredHours(catalog: PresenceCatalog, range: TimeRange): number[]
export function nextCovered(hours: number[], cursor: number, direction?: number): number | null
export function requiredDays(cursor: number, rangeStart: number, catalog: PresenceCatalog): PresenceDay[]
export function currentObservations(observations: Observation[], cursor: number): Observation[]
export function trailFeatures(observations: Observation[], vesselId: string | null, cursor: number, rangeStart: number): any
export function mergeVessels(summaries: DayVessels[]): PresenceVessel[]
export function createLatestRequest(): { invalidate(): void; run<T>(work: () => Promise<T>, publish: (value: T) => void, reject: (error: unknown) => void): Promise<void> }
