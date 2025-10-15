/**
 * Mock model endpoints store
 * These represent API endpoints where models are deployed and accessible
 */

export interface ModelEndpoint {
  id: string
  name: string
  description?: string
  modelIds: string[]
  url?: string
  status?: 'active' | 'inactive'
  createdAt?: Date
}

export const mockModelEndpoints: ModelEndpoint[] = [
  {
    id: 'endpoint-1',
    name: 'Document Analysis API',
    description: 'Analyze and extract insights from documents',
    modelIds: ['nlp-engine'],
    url: '/api/v1/document-analysis',
    status: 'active',
    createdAt: new Date('2024-01-25')
  },
  {
    id: 'endpoint-2', 
    name: 'Content Generation API',
    description: 'Generate content using AI models',
    modelIds: ['nlp-engine'],
    url: '/api/v1/content-generation',
    status: 'active',
    createdAt: new Date('2024-02-01')
  },
  {
    id: 'endpoint-3',
    name: 'Code Review Assistant',
    description: 'AI-powered code review and suggestions',
    modelIds: ['code-assistant'],
    url: '/api/v1/code-review',
    status: 'active',
    createdAt: new Date('2024-02-10')
  }
]

// Utility functions for working with model endpoints
export const getEndpointsForModel = (modelId: string): ModelEndpoint[] => {
  return mockModelEndpoints.filter(endpoint => 
    endpoint.modelIds.includes(modelId)
  )
}

export const getEndpointById = (endpointId: string): ModelEndpoint | undefined => {
  return mockModelEndpoints.find(endpoint => endpoint.id === endpointId)
}

export const getActiveEndpoints = (): ModelEndpoint[] => {
  return mockModelEndpoints.filter(endpoint => endpoint.status === 'active')
}