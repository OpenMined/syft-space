/**
 * Mock agents store
 * An Agent is a local resource: a session orchestrator (Claude / Codex) plus the
 * skills, MCPs and folders it has been granted access to. Like Data Sources and
 * Models, an Agent can be turned into an API.
 */
import { reactive } from 'vue'

export type Orchestrator = 'claude' | 'codex'

export interface Agent {
  id: string
  name: string
  description: string
  tags: string[]
  orchestrator: Orchestrator
  skills: string[]
  mcps: string[]
  folders: string[]
  status: 'active' | 'inactive'
  sessions: number
  lastUpdated: Date
  endpointCount: number
}

export const ORCHESTRATORS: { id: Orchestrator; label: string }[] = [
  { id: 'claude', label: 'Claude' },
  { id: 'codex', label: 'Codex' },
]

export const getOrchestratorLabel = (id: Orchestrator): string =>
  ORCHESTRATORS.find((o) => o.id === id)?.label ?? id

// Pools the create dialog imports from (checkbox-selectable access).
export const AVAILABLE_SKILLS = [
  'web-search',
  'code-review',
  'deep-research',
  'summarize',
  'calendar',
  'email-triage',
]
export const AVAILABLE_MCPS = ['filesystem', 'github', 'slack', 'gmail', 'notion', 'postgres']
export const AVAILABLE_FOLDERS = ['~/Documents', '~/Projects', '~/Downloads', '~/Desktop']

export const mockAgents = reactive<Agent[]>([
  {
    id: 'personal-assistant',
    name: 'Personal Assistant',
    description:
      'Day-to-day Claude orchestrator that triages messages, drafts replies and keeps your projects moving.',
    tags: ['assistant', 'productivity'],
    orchestrator: 'claude',
    skills: ['web-search', 'summarize', 'email-triage'],
    mcps: ['filesystem', 'gmail', 'slack'],
    folders: ['~/Documents', '~/Projects'],
    status: 'active',
    sessions: 3,
    lastUpdated: new Date('2026-06-10'),
    endpointCount: 1,
  },
  {
    id: 'research-agent',
    name: 'Research Agent',
    description:
      'Long-running research orchestrator that fans out web searches and synthesizes cited reports.',
    tags: ['research', 'analysis'],
    orchestrator: 'claude',
    skills: ['deep-research', 'web-search', 'summarize'],
    mcps: ['filesystem', 'notion'],
    folders: ['~/Documents'],
    status: 'active',
    sessions: 1,
    lastUpdated: new Date('2026-06-08'),
    endpointCount: 0,
  },
  {
    id: 'code-helper',
    name: 'Code Helper',
    description: 'Codex orchestrator wired to your repos for reviews and refactors.',
    tags: ['coding'],
    orchestrator: 'codex',
    skills: ['code-review'],
    mcps: ['github', 'filesystem'],
    folders: ['~/Projects'],
    status: 'inactive',
    sessions: 0,
    lastUpdated: new Date('2026-05-30'),
    endpointCount: 0,
  },
])

export const getAgentById = (agentId: string): Agent | undefined =>
  mockAgents.find((agent) => agent.id === agentId)

export const searchAgents = (query: string): Agent[] => {
  const term = query.toLowerCase()
  return mockAgents.filter(
    (agent) =>
      agent.name.toLowerCase().includes(term) ||
      agent.description.toLowerCase().includes(term) ||
      agent.tags.some((tag) => tag.toLowerCase().includes(term)),
  )
}
