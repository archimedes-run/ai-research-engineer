// Static mode/domain lists + mode→payload mapping.
// Consumed by the cockpit launcher and any future form surfaces.

export const MODES = [
  {
    value: 'novel',
    label: 'Novel Research',
    description: 'Generate new ideas, hypotheses, and architectures',
  },
  {
    value: 'replication',
    label: 'Replication',
    description: 'Reproduce and verify existing paper results',
  },
  {
    value: 'evolve',
    label: 'Evolutionary',
    description: 'Iterative Darwinian optimization over generations',
  },
] as const

export type Mode = (typeof MODES)[number]['value']

export const DOMAINS = [
  { value: 'aiml', label: 'AI / ML' },
  { value: 'algorithms', label: 'Algorithms' },
  { value: 'bioinformatics', label: 'Bioinformatics' },
  { value: 'finance', label: 'Finance' },
  { value: 'physics', label: 'Physics' },
] as const

export type Domain = (typeof DOMAINS)[number]['value']

// Maps a frontend mode to the backend RunSessionRequest fields.
// §1.1 from the cockpit addendum:
//   novel        → research_mode: "novelty",  agent_type: "adk" (default)
//   replication  → research_mode: "replication", agent_type: "adk" (default)
//   evolve       → agent_type: "evolve" (backend derives research_mode internally)
export function modeToPayload(mode: Mode): {
  agent_type?: string
  research_mode?: string
} {
  switch (mode) {
    case 'novel':
      return { research_mode: 'novelty' }
    case 'replication':
      return { research_mode: 'replication' }
    case 'evolve':
      return { agent_type: 'evolve' }
  }
}
