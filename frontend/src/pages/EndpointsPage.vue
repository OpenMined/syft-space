<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <Server class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Endpoints</h1>
    </div>
    <p class="text-gray-600 mb-8">Manage how you share your datasets and models with your users</p>

    <!-- Header with tabs and search bar -->
    <div class="flex items-center justify-between gap-4 mb-8">
      <!-- Tabs -->
      <Tabs v-model="activeTab" class="w-auto">
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]">
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="published">Published</TabsTrigger>
          <TabsTrigger value="draft">Draft</TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Search bar and Create button -->
      <div class="flex items-center gap-4">
        <div class="relative w-80">
          <Search class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <Input v-model="searchQuery" placeholder="Find endpoints, tags, owners..." class="pl-10 pr-4 py-2 w-full" />
        </div>

        <!-- Create Endpoint Button -->
        <Button @click="router.push({ name: 'create' })" class="bg-purple-600 hover:bg-purple-700 text-white">
          <Plus class="h-4 w-4 mr-2" />
          Create Endpoint
        </Button>
      </div>
    </div>

    <!-- Endpoint cards -->
    <div class="space-y-4">
      <EndpointCard v-for="endpoint in filteredEndpoints" :key="endpoint.id" :endpoint="endpoint" />
    </div>

    <!-- DEMO: Empty State Section -->
    <div class="mt-16">
      <!-- Divider with centered text -->
      <div class="relative">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-gray-300"></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-4 bg-gray-50 text-gray-600 font-medium">
            Demo: Empty State (shown when no endpoints exist)
          </span>
        </div>
      </div>

      <!-- Empty state content -->
      <div class="mt-8 bg-white rounded-lg shadow border border-gray-200 p-8 text-center">
        <Server class="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">No endpoints created</h3>
        <p class="text-gray-600 mb-4">Create your first endpoint to start sharing datasets or AI models</p>
        <Button @click="router.push({ name: 'create' })" class="bg-purple-600 hover:bg-purple-700 text-white">
          <Plus class="h-4 w-4 mr-2" />
          Create Endpoint
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Plus, Server } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import EndpointCard from '@/components/EndpointCard.vue'
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'

const router = useRouter()
const endpointsStore = useEndpointsStore()



const searchQuery = ref('')
const activeTab = ref('all')

const filteredEndpoints = computed(() => {
  return endpointsStore.endpoints.filter((endpoint: EndpointItem) => {
    // Search query filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      if (
        !endpoint.name.toLowerCase().includes(query) &&
        !endpoint.summary.toLowerCase().includes(query)
      ) {
        return false
      }
    }

    // Tab filter
    if (activeTab.value === 'published' && endpoint.status !== 'published') {
      return false
    }
    if (activeTab.value === 'draft' && endpoint.status !== 'draft') {
      return false
    }

    return true
  })
})
</script>
