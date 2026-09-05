import { vessels as mockVessels } from './mockData'
import type { Vessel } from '../types'

export interface RiskDataProvider { getRiskEvents(): Promise<Vessel[]> }

const mockProvider: RiskDataProvider = { getRiskEvents: async () => mockVessels }
const apiProvider: RiskDataProvider = {
  async getRiskEvents() {
    const base = import.meta.env.VITE_API_BASE_URL ?? ''
    const response = await fetch(`${base}/risk-events`)
    if (!response.ok) throw new Error('Risk events could not be loaded')
    return response.json() as Promise<Vessel[]>
  }
}

export const dataProvider = import.meta.env.VITE_DATA_MODE === 'api' ? apiProvider : mockProvider
