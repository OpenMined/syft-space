<template>
  <div class="max-w-6xl mx-auto px-6 lg:px-8 py-8 lg:py-12">
    <!-- Hero Section with Help -->
    <div class="mb-10">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-3">
            <Server class="h-6 w-6 text-[var(--color-accent)]" />
            <h1 class="text-2xl font-bold text-gray-900">Your Endpoints</h1>
          </div>
          <p class="text-gray-600 md:max-w-[50%]">Endpoints are the way to safely share your datasets and models. Create as many as you need per resource, each with its own rules, access controls, and tracking.</p>
        </div>
        <div class="flex items-center gap-3">
          <!-- Help Info -->
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <button class="p-2 text-[var(--color-text-light)] hover:text-[var(--color-text)] transition-colors">
                  <HelpCircle class="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left" class="max-w-xs">
                <p class="font-medium mb-1">What are endpoints?</p>
                <p class="text-xs">Endpoints are your shared content (documents, databases) or AI models that others can access through APIs. You control who can use them and can set pricing.</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    </div>

    <!-- Moved analytics summary to Analytics page -->

    <!-- Filters Bar (match Models styling) -->
    <div class="mb-8">
      <div class="flex items-center justify-between gap-4">
        <!-- Tabs -->
        <Tabs v-model:value="activeTab" class="w-auto">
          <TabsList
            class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]"
          >
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="published">Published</TabsTrigger>
            <TabsTrigger value="draft">Draft</TabsTrigger>
          </TabsList>
        </Tabs>

        <!-- Search -->
        <div class="flex items-center gap-4">
          <div class="relative w-80">
            <Search
              class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400"
            />
            <Input
              v-model="searchQuery"
              placeholder="Search endpoints..."
              class="pl-10 pr-4 py-2.5 w-full bg-[var(--color-bg-alt)] border-[var(--color-border)] rounded-lg focus:bg-[var(--color-bg-light)] transition-colors"
            />
          </div>
          <Button
            class="bg-[var(--color-accent)] hover:bg-[var(--color-accent-strong)] text-white px-5 py-2.5 rounded-lg shadow-sm hover:shadow-md transition-all"
            @click="showCreateEndpointModal = true"
          >
            <Plus class="h-4 w-4 mr-2" />
            Add Endpoint
          </Button>
        </div>
      </div>
    </div>

    <!-- Endpoint cards -->
    <div class="space-y-5">
      <EndpointCard v-for="endpoint in filteredEndpoints" :key="endpoint.id" :endpoint="endpoint" />
    </div>

    <!-- DEMO: Empty State Section -->
    <div class="mt-16">
      <!-- Divider with centered text -->
      <div class="relative">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-[var(--color-border)]"></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-4 bg-[var(--color-bg)] text-[var(--color-text-light)] font-medium">
            Demo: Empty State (shown when no endpoints exist)
          </span>
        </div>
      </div>

      <!-- Empty state (like GitHub's empty repo) -->
      <div class="mt-8 text-center py-12">
        <div class="mx-auto w-14 h-14 bg-[var(--color-bg-alt)] rounded-full flex items-center justify-center mb-6">
          <Server class="w-7 h-7 text-[var(--color-text-light)]" />
        </div>
        <h3 class="text-xl font-heading font-medium text-[var(--color-text)] mb-3">No endpoints yet</h3>
        <p class="text-sm text-[var(--color-text-light)] mb-8 max-w-sm mx-auto">
          Get started by creating your first endpoint to share data or models.
        </p>
        <div class="flex items-center justify-center gap-3">
          <Button
            @click="showCreateEndpointModal = true"
            class="bg-[var(--color-success)] hover:bg-[var(--color-success-strong)] text-white font-medium px-6 py-2.5 rounded-lg shadow-sm hover:shadow-md transition-all"
          >
            <Plus class="h-4 w-4 mr-2" />
            Create your first endpoint
          </Button>
          <Button variant="outline" class="text-[var(--color-text-light)] hover:text-[var(--color-text)] border-[var(--color-border)] px-6 py-2.5 rounded-lg">
            Learn more
          </Button>
        </div>
      </div>
    </div>
  </div>

  <!-- Create Endpoint Modal -->
  <CreateEndpointModal v-model:open="showCreateEndpointModal" />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Plus, Server, HelpCircle } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import EndpointCard from '@/components/EndpointCard.vue'
import CreateEndpointModal from '@/components/CreateEndpointModal.vue'
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'

const endpointsStore = useEndpointsStore()

const searchQuery = ref('')
const activeTab = ref('all')
const showCreateEndpointModal = ref(false)

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
