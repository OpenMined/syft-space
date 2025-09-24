import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ServiceItem {
  id: string
  type: 'data-source' | 'synthesizer'
  name: string
  description: string
  price: string
  supportedServices: string[]
  languages: string[]
  domains: string[]
  mcpCompatible: boolean
  tags: string[]
  status: 'published' | 'draft'
}

export const useServicesStore = defineStore('services', () => {
  const services = ref<ServiceItem[]>([
    {
      id: '1',
      type: 'data-source',
      name: 'research@safari-lab.org/animalsofsouthafrica',
      description: 'Species records, park reports, conservation notes.',
      price: '$0.005 / request',
      supportedServices: ['search', 'rag'],
      languages: ['english'],
      domains: ['wildlife'],
      mcpCompatible: true,
      tags: ['domain:wildlife'],
      status: 'published',
    },
    {
      id: '2',
      type: 'data-source',
      name: 'data@lexfirm.eu/lexcivillaw',
      description: 'Civil code, case law digests, firm memos (EU focus).',
      price: '$0.010 / request',
      supportedServices: ['search', 'rag'],
      languages: ['english', 'german', 'french'],
      domains: ['legal'],
      mcpCompatible: false,
      tags: ['domain:legal', 'language:de'],
      status: 'published',
    },
    {
      id: '3',
      type: 'data-source',
      name: 'admin@st-marys-hospital.com/meddevicerecords',
      description: 'Hospital device logs, maintenance + UDI registry links.',
      price: '$0.02 / request',
      supportedServices: ['search'],
      languages: ['english'],
      domains: ['healthcare'],
      mcpCompatible: false,
      tags: ['domain:healthcare'],
      status: 'draft',
    },
  ])

  const publishedServices = computed(() => services.value.filter((s) => s.status === 'published'))

  return {
    services,
    publishedServices,
  }
})
