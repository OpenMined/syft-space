/**
 * Mock datasets store
 * Centralized dataset data for consistency across components
 */

export interface Dataset {
  id: string
  name: string
  description: string
  tags: string[]
  status: 'published' | 'draft'
  records: number
  size: string
  lastUpdated: Date
  isPrivate?: boolean
  owner?: string
  endpointCount?: number
}

export const mockDatasets: Dataset[] = [
  {
    id: 'animals-south-africa',
    name: 'Animals of South Africa',
    description:
      'Comprehensive database of South African wildlife including species records, habitat information, and conservation status across all major ecosystems.',
    tags: ['wildlife', 'conservation', 'biology'],
    status: 'published',
    records: 12847,
    size: '2.3 GB',
    lastUpdated: new Date('2024-01-15'),
    isPrivate: false,
    owner: 'Safari Research Lab',
  },
  {
    id: 'legal-documents',
    name: 'Legal Document Database',
    description:
      'Collection of legal documents, case studies, and regulatory frameworks from various jurisdictions worldwide.',
    tags: ['legal', 'documents', 'regulatory'],
    status: 'published',
    records: 8945,
    size: '1.8 GB',
    lastUpdated: new Date('2024-01-10'),
    isPrivate: false,
    owner: 'Legal Research Institute',
  },
  {
    id: 'medical-research',
    name: 'Medical Research Papers',
    description:
      'Curated collection of peer-reviewed medical research papers and clinical trial data for healthcare AI applications.',
    tags: ['medical', 'research', 'healthcare'],
    status: 'draft',
    records: 15623,
    size: '4.1 GB',
    lastUpdated: new Date('2024-01-20'),
    isPrivate: true,
    owner: 'Medical AI Consortium',
  },
  {
    id: 'financial-reports',
    name: 'Corporate Financial Reports',
    description:
      'Annual and quarterly financial reports from publicly traded companies across multiple sectors and geographic regions.',
    tags: ['finance', 'corporate', 'analysis'],
    status: 'published',
    records: 5672,
    size: '892 MB',
    lastUpdated: new Date('2024-01-12'),
    isPrivate: false,
    owner: 'FinData Analytics',
  },
]

// Utility functions for working with datasets
export const getPublishedDatasets = (): Dataset[] => {
  return mockDatasets.filter((dataset) => dataset.status === 'published')
}

export const getDraftDatasets = (): Dataset[] => {
  return mockDatasets.filter((dataset) => dataset.status === 'draft')
}

export const getDatasetById = (datasetId: string): Dataset | undefined => {
  return mockDatasets.find((dataset) => dataset.id === datasetId)
}

export const getDatasetsByTag = (tag: string): Dataset[] => {
  return mockDatasets.filter((dataset) =>
    dataset.tags.some((t) => t.toLowerCase().includes(tag.toLowerCase())),
  )
}

export const searchDatasets = (query: string): Dataset[] => {
  const searchTerm = query.toLowerCase()
  return mockDatasets.filter(
    (dataset) =>
      dataset.name.toLowerCase().includes(searchTerm) ||
      dataset.description.toLowerCase().includes(searchTerm) ||
      dataset.tags.some((tag) => tag.toLowerCase().includes(searchTerm)),
  )
}
