import type { RiskEvent } from '../types'

export interface RiskDataProvider {
  getRiskEvents(signal?: AbortSignal): Promise<RiskEvent[]>
}

const staticProvider: RiskDataProvider = {
  async getRiskEvents(signal) {
    let response: Response
    try {
      response = await fetch(`${import.meta.env.BASE_URL}data/risk-events.json`, { signal })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new Error('The GapPair export could not be reached. Check that data/risk-events.json is deployed with the frontend.')
    }
    if (!response.ok) {
      throw new Error(`The GapPair export could not be loaded (${response.status} ${response.statusText || 'request failed'}).`)
    }
    let payload: unknown
    try {
      payload = await response.json()
    } catch {
      throw new Error('The GapPair export is not valid JSON. Regenerate data/risk-events.json and retry.')
    }
    if (!Array.isArray(payload)) {
      throw new Error('The GapPair export has an unsupported format: expected an array of pair records.')
    }
    return payload as RiskEvent[]
  },
}

// Risk events are a bundled static artifact. There is intentionally no
// undeployed /risk-events API fallback and no mock-data default.
export const dataProvider = staticProvider
