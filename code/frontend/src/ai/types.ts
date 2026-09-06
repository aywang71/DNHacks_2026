export interface ShipTarget { vesselId: string; caseId?: string; start?: string; end?: string }
export interface AiSource { id: string; label: string; detail: string }
export interface ShipContext {
  vessel: { id: string; name?: string | null; mmsi?: string | null; observationCount: number }
  window: { start: string; end: string; endExclusive: boolean }
  presence: { observationCount: number; sampleCount: number; importedHours: number; unimportedHours: number; coveredEmptyHours: number; vesselObservedHours: number }
  analystNotes: string
  sources: AiSource[]
}
export interface AiResult {
  title: string; summary: string
  sections: { heading: string; text: string; sourceIds: string[] }[]
  suggestedQuestions: string[]; model: string; generatedAt: string; context: ShipContext
}
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
