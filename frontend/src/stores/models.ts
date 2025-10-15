import { MODEL_TYPES, STATUS_OPTIONS, type ValueOf, type OptionalTimestampField } from '@/lib/constants'

export interface Model {
  id: string
  name: string
  type: ValueOf<typeof MODEL_TYPES>
  description: string
  tags: string[]
  status: ValueOf<typeof STATUS_OPTIONS>
  endpointCount: number
  createdAt?: OptionalTimestampField
}

export const mockModels: Model[] = [
  {
    id: 'nlp-engine',
    name: 'NLP Processing Engine',
    type: 'vllm',
    description: 'Large language model for natural language processing',
    tags: ['nlp', 'analysis'],
    status: 'stopped',
    endpointCount: 2,
    createdAt: new Date('2024-01-20')
  },
  {
    id: 'code-assistant',
    name: 'Code Assistant Model',
    type: 'ollama',
    description: 'Local code generation and programming assistance',
    tags: ['code', 'programming'],
    status: 'running',
    endpointCount: 1,
    createdAt: new Date('2024-02-05')
  },
  {
    id: 'text-embedding',
    name: 'Text Embedding Service',
    type: 'huggingface',
    description: 'High-quality text embeddings for semantic search and similarity',
    tags: ['embeddings', 'semantic'],
    status: 'stopped',
    endpointCount: 0,
    createdAt: new Date('2024-03-01')
  }
]