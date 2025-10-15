/**
 * Centralized mock data store
 * Common mock data used across multiple components
 */

// Mock analytics data
export interface AnalyticsData {
  totalRequests: string
  successRate: string
  thisMonth: string
  activeUsers: string
  totalEarnings: string
  monthlyEarnings: string
  growth: string
}

export const getMockAnalytics = (entityType: 'model' | 'dataset' | 'endpoint'): AnalyticsData => {
  // Different mock data based on entity type
  const baseData = {
    model: {
      totalRequests: '23.7k',
      successRate: '97.3%',
      thisMonth: '5.2k',
      activeUsers: '156',
      totalEarnings: '$1,247.85',
      monthlyEarnings: '$312.40',
      growth: '+8.1%',
    },
    dataset: {
      totalRequests: '18.3k',
      successRate: '98.7%',
      thisMonth: '4.1k',
      activeUsers: '89',
      totalEarnings: '$892.40',
      monthlyEarnings: '$245.80',
      growth: '+12.3%',
    },
    endpoint: {
      totalRequests: '45.2k',
      successRate: '96.1%',
      thisMonth: '8.7k',
      activeUsers: '234',
      totalEarnings: '$2,145.60',
      monthlyEarnings: '$567.20',
      growth: '+15.7%',
    },
  }

  return baseData[entityType]
}

// Mock endpoint distribution data for charts
export interface EndpointDistribution {
  name: string
  percentage: number
  color: string
  requests: string
}

export const getMockEndpointDistribution = (modelId?: string): EndpointDistribution[] => {
  // Different distributions based on model
  const distributions = {
    'nlp-engine': [
      { name: 'Document Analysis API', percentage: 65, color: '#3B82F6', requests: '15.4k' },
      { name: 'Content Generation API', percentage: 35, color: '#10B981', requests: '8.3k' },
    ],
    'code-assistant': [
      { name: 'Code Review Assistant', percentage: 100, color: '#F59E0B', requests: '12.1k' },
    ],
    'text-embedding': [
      { name: 'Semantic Search API', percentage: 70, color: '#8B5CF6', requests: '8.9k' },
      { name: 'Document Similarity API', percentage: 30, color: '#EF4444', requests: '3.8k' },
    ],
    default: [{ name: 'Primary API', percentage: 100, color: '#6B7280', requests: '0' }],
  }

  return distributions[modelId as keyof typeof distributions] || distributions.default
}

// Common color schemes
export const colorSchemes = {
  status: {
    running: 'bg-green-50 text-green-700 border-green-200',
    stopped: 'bg-gray-50 text-gray-600 border-gray-200',
    published: 'bg-blue-50 text-blue-700 border-blue-200',
    draft: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  },
  modelType: {
    vllm: 'bg-purple-100',
    ollama: 'bg-orange-100',
    huggingface: 'bg-indigo-100',
  },
}

// Mock performance metrics
export interface PerformanceMetrics {
  accuracy?: string
  latency: string
  throughput: string
  uptime?: string
}

export const getMockPerformanceMetrics = (entityType: 'model' | 'endpoint'): PerformanceMetrics => {
  const metrics = {
    model: {
      accuracy: '94.2%',
      latency: '250ms',
      throughput: '15 req/s',
      uptime: '99.8%',
    },
    endpoint: {
      latency: '180ms',
      throughput: '32 req/s',
      uptime: '99.9%',
    },
  }

  return metrics[entityType]
}
