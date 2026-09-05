import type { PresenceDataProvider } from './types'
export function createPresenceProvider(base?: string, fetcher?: typeof fetch): PresenceDataProvider
