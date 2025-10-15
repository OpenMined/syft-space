import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { DATA_SOURCE_TYPES, MODEL_TYPES, STATUS_OPTIONS, type ValueOf } from '@/lib/constants'

export interface EndpointItem {
  id: string
  name: string
  summary: string
  description: string
  dataSourceType?: ValueOf<typeof DATA_SOURCE_TYPES>
  modelType?: ValueOf<typeof MODEL_TYPES>
  price: string
  languages: string[]
  domains: string[]
  mcpCompatible: boolean
  tags: string[]
  status: ValueOf<typeof STATUS_OPTIONS>
}

export const useEndpointsStore = defineStore('endpoints', () => {
  const endpoints = ref<EndpointItem[]>([
    {
      id: '1',
      name: 'animalsofsouthafrica',
      summary: 'Species records, park reports, conservation notes.',
      description: `This dataset contains comprehensive information about the diverse wildlife found across South Africa's various ecosystems, from the arid Karoo to the lush coastal regions.

### Data Sources

• Field research conducted by Safari Lab researchers
• Collaboration with local conservation organizations
• Historical records from national parks and reserves
• Citizen science contributions and sightings

### Coverage

The dataset covers 9 provinces with varying levels of detail based on research intensity and accessibility. Marine species data is particularly strong along the Western Cape coastline.

### Quality Assurance

All entries undergo verification by trained biologists and cross-referencing with established databases. GPS coordinates are validated against known habitat ranges.

### Dataset Statistics

2.3M+ Total Records
847 Species
23 National Parks
15 Years of Data`,
      dataSourceType: 'weaviate',
      modelType: 'vllm',
      price: '$0.005 - $0.015 / request',
      languages: ['english'],
      domains: ['wildlife'],
      mcpCompatible: true,
      tags: ['domain:wildlife'],
      status: 'published',
    },
    {
      id: '2',
      name: 'lexcivillaw',
      summary: 'Civil code, case law digests, firm memos (EU focus).',
      description: `This dataset contains comprehensive European civil law materials including case law, civil codes, legal commentary, and regulatory frameworks from across the European Union and associated jurisdictions.

### Data Sources

• Official court decisions and judgments from EU member states
• National civil codes and statutory legislation
• Legal commentary and academic analysis
• EU regulatory instruments and directives

### Coverage

The dataset covers 27 EU member states plus associated jurisdictions, with comprehensive coverage of contract law, property rights, tort liability, and civil procedure. German and French legal systems are particularly well-represented.

### Quality Assurance

All legal documents undergo verification by qualified legal professionals and cross-referencing with official legal databases. Citations and references are validated against established legal authorities.

### Dataset Statistics

849K+ Total Records
28 Jurisdictions
12 Languages
8 Legal Areas`,
      dataSourceType: 'qdrant',
      modelType: 'ollama',
      price: '$0.008 - $0.025 / request',
      languages: ['english', 'german', 'french'],
      domains: ['legal'],
      mcpCompatible: false,
      tags: ['domain:legal', 'language:de'],
      status: 'published',
    },
    {
      id: '3',
      name: 'meddevicerecords',
      summary: 'Hospital device logs, maintenance + UDI registry links.',
      description: `This dataset contains comprehensive information about medical devices and equipment used across St. Mary's Hospital network, including installation records, maintenance schedules, and operational status.

### Data Sources

• Hospital equipment management systems
• Manufacturer installation records
• Maintenance service logs
• Equipment inventory audits

### Coverage

The dataset covers all major departments including emergency, intensive care, radiology, and surgical units. Imaging equipment and life support systems are particularly well-documented.

### Quality Assurance

All records undergo verification by biomedical engineers and cross-referencing with manufacturer databases. Serial numbers and installation dates are validated against official documentation.

### Dataset Statistics

847K+ Total Records
156 Device Types
12 Departments
8 Years of Data`,
      dataSourceType: 'filesystem',
      price: '$0.015 - $0.040 / request',
      languages: ['english'],
      domains: ['healthcare'],
      mcpCompatible: false,
      tags: ['domain:healthcare'],
      status: 'draft',
    },
  ])

  return {
    endpoints,
  }
})
