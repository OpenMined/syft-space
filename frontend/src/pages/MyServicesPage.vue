<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header with tabs and search bar -->
    <div class="flex items-center justify-between gap-4 mb-8">
      <!-- Tabs -->
      <Tabs v-model="activeTab" class="w-auto">
        <TabsList class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]">
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="published">Published</TabsTrigger>
          <TabsTrigger value="draft">Draft</TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Search bar -->
      <div class="relative w-80">
        <Search class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
        <Input
          v-model="searchQuery"
          placeholder="Find services, tags, owners..."
          class="pl-10 pr-4 py-2 w-full"
        />
      </div>
    </div>

    <!-- Service cards -->
    <div class="space-y-4">
      <ServiceCard
        v-for="service in filteredServices"
        :key="service.id"
        :service="service"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import ServiceCard from '@/components/ServiceCard.vue'

interface Service {
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

// Mock data for services
const services = ref<Service[]>([
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
    status: 'published'
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
    status: 'published'
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
    status: 'draft'
  }
])

const searchQuery = ref('')
const activeTab = ref('all')

const filteredServices = computed(() => {
  return services.value.filter(service => {
    // Search query filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      if (!service.name.toLowerCase().includes(query) &&
          !service.description.toLowerCase().includes(query)) {
        return false
      }
    }

    // Tab filter
    if (activeTab.value === 'published' && service.status !== 'published') {
      return false
    }
    if (activeTab.value === 'draft' && service.status !== 'draft') {
      return false
    }

    return true
  })
})
</script>