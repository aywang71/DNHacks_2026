import type { RiskEvent, Scores } from '../types'

export type ScoreKey = 'geom' | 'kin' | 'beh' | 'ctx' | 'cor' | 'den' | 'flt' | 'hab'
export type AnalystWeights = Record<ScoreKey, number>

export interface ScoreComponentDefinition {
  key: ScoreKey
  shortLabel: string
  label: string
  fallbackReason: string
  unavailableReason: string
  terms: RegExp
}

export const DEFAULT_WEIGHTS: AnalystWeights = {
  geom: 0.30,
  kin: 0.15,
  beh: 0.20,
  ctx: 0.15,
  cor: 0.20,
  den: -0.15,
  flt: -0.20,
  hab: -0.10,
}

export const SCORE_COMPONENTS: ScoreComponentDefinition[] = [
  {
    key: 'geom', shortLabel: 'Geometry', label: 'Geometry / null rarity',
    fallbackReason: 'Within-cell permutation rarity from p_cell. It describes an unusual paired count under the null model, not wrongdoing.',
    unavailableReason: 'No p_cell-based geometry score was supplied, so geometry is excluded rather than treated as zero.',
    terms: /geometry|p[_ ]?cell|within.cell|permutation|null model|rarity/i,
  },
  {
    key: 'kin', shortLabel: 'Kinematics', label: 'Kinematic feasibility',
    fallbackReason: 'Whether feasible movement fits the configured class speed. It is a gate and loose-rule feature, not affirmative evidence.',
    unavailableReason: 'No kinematic score was supplied, so it is excluded rather than treated as zero.',
    terms: /kinematic|required speed|joint dwell|feasib/i,
  },
  {
    key: 'beh', shortLabel: 'Behaviour', label: 'Behavioural context',
    fallbackReason: 'Not available here: GFW loitering, encounter, and port-visit events were not pulled for these vessels.',
    unavailableReason: 'Behaviour is unavailable because the export does not include the source events needed to calculate it; it is excluded rather than treated as zero.',
    terms: /behaviou?r|loiter|encounter|port.visit|port.after/i,
  },
  {
    key: 'ctx', shortLabel: 'Context', label: 'Context / flag history',
    fallbackReason: 'Cross-flag, carding, authorization, IUU-list, and port-risk context where available.',
    unavailableReason: 'No context score was supplied, so it is excluded rather than treated as zero.',
    terms: /context|cross.flag|flag.history|card|authori[sz]|iuu|port risk/i,
  },
  {
    key: 'cor', shortLabel: 'Corroboration', label: 'Imagery corroboration',
    fallbackReason: 'Only an uncorrelated VIIRS detection inside the inferred reachable sets scores here.',
    unavailableReason: 'No imagery-corroboration score was supplied, so it is excluded rather than treated as zero.',
    terms: /viirs|imagery|corrobor|detection/i,
  },
  {
    key: 'den', shortLabel: 'Density', label: 'Local density penalty',
    fallbackReason: 'Local dark-event density is a penalty. It is not the null model and does not establish a cause for the gap.',
    unavailableReason: 'No local-density penalty was supplied, so it is excluded rather than treated as zero.',
    terms: /density|other vessel|local dark|200 km/i,
  },
  {
    key: 'flt', shortLabel: 'Fleet', label: 'Fleet/confounder penalty',
    fallbackReason: 'Fleet clustering, sequential MMSIs, identity twins, or strongly same-flag local context are penalties.',
    unavailableReason: 'No fleet/confounder penalty was supplied, so it is excluded rather than treated as zero.',
    terms: /fleet|sequential|identity twin|same.flag|cluster/i,
  },
  {
    key: 'hab', shortLabel: 'Habitual', label: 'Gap-history penalty',
    fallbackReason: 'A penalty based on gap unusualness. It does not identify an act during this gap.',
    unavailableReason: 'No gap-history penalty was supplied, so it is excluded rather than treated as zero.',
    terms: /unusual|habit|history|repeat/i,
  },
]

export interface WeightedComponent {
  definition: ScoreComponentDefinition
  value: number | null
  weight: number
  contribution: number | null
  reason: string
}

export interface AnalystScore {
  raw: number | null
  priority: number | null
  normalizer: number | null
  availableWeightMass: number
  totalWeightMass: number
  components: WeightedComponent[]
}

const isScore = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)

function textFrom(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (Array.isArray(value)) {
    const text = value.map(textFrom).filter((item): item is string => item !== null).join(' ')
    return text || null
  }
  if (isRecord(value)) {
    return textFrom(value.reason) ?? textFrom(value.explanation) ?? textFrom(value.detail) ?? textFrom(value.text)
  }
  return null
}

function componentProvenance(event: RiskEvent, key: ScoreKey): string | null {
  for (const sibling of ['componentExplanations', 'scoreExplanations', 'scoreProvenance', 'provenance']) {
    const record = event[sibling]
    if (!isRecord(record)) continue
    const item = textFrom(record[key]) ?? textFrom(record[`${key}Reason`])
    if (item) return item
  }
  return null
}

export function componentReason(event: RiskEvent, definition: ScoreComponentDefinition): string {
  const value = event.scores[definition.key]
  const supplied = componentProvenance(event, definition.key)
  if (!isScore(value)) return supplied ? `${supplied} This term is excluded rather than treated as zero.` : definition.unavailableReason
  if (supplied) return supplied
  const explanation = event.explanations.find((item) => definition.terms.test(item))
  return explanation ?? definition.fallbackReason
}

/**
 * Match the pipeline calculation: divide the signed weighted sum by the
 * absolute weight mass of only scored terms. A null score is absent evidence,
 * never an implicit zero.
 */
export function calculateAnalystScore(scores: Scores, weights: AnalystWeights, event?: RiskEvent): AnalystScore {
  const availableWeightMass = SCORE_COMPONENTS.reduce((sum, definition) => {
    const value = scores[definition.key]
    return sum + (isScore(value) ? Math.abs(weights[definition.key]) : 0)
  }, 0)
  const totalWeightMass = SCORE_COMPONENTS.reduce((sum, definition) => sum + Math.abs(weights[definition.key]), 0)
  const normalizer = availableWeightMass > 0 ? 1 / availableWeightMass : null
  const components = SCORE_COMPONENTS.map((definition) => {
    const value = scores[definition.key]
    const usable = isScore(value)
    return {
      definition,
      value: usable ? value : null,
      weight: weights[definition.key],
      contribution: usable && normalizer !== null ? value * weights[definition.key] * normalizer : null,
      reason: event ? componentReason(event, definition) : definition.fallbackReason,
    }
  })
  const raw = normalizer === null ? null : components.reduce((sum, component) => sum + (component.contribution ?? 0), 0)
  // The pipeline's priority transform is an analyst-priority aid, not a
  // probability. We retain it only to give a familiar, monotonic live rank.
  const priority = raw === null ? null : 1 / (1 + Math.exp(-6 * (raw - 0.30)))
  return { raw, priority, normalizer, availableWeightMass, totalWeightMass, components }
}

export function scoresEqual(left: AnalystWeights, right: AnalystWeights): boolean {
  return SCORE_COMPONENTS.every(({ key }) => left[key] === right[key])
}
