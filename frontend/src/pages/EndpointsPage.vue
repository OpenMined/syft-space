<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Hero Section with Help -->
    <div class="mb-10">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-3">
            <Server class="h-6 w-6 text-primary" />
            <h1 class="heading-3">Your Endpoints</h1>
          </div>
          <p class="body-lg text-muted-foreground md:max-w-[50%]">
            Endpoints are the way to safely share your datasets and models. Create as many as you
            need per resource, each with its own rules, access controls, and tracking.
          </p>
        </div>
        <div class="flex items-center gap-3">
          <!-- Help Info -->
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <button class="p-2 text-muted-foreground hover:text-foreground transition-colors">
                  <HelpCircle class="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left" class="max-w-xs">
                <p class="body-base font-semibold mb-1">What are endpoints?</p>
                <p class="body-sm">
                  Endpoints are your shared content (documents, databases) or AI models that others
                  can access through APIs. You control who can use them and can set pricing.
                </p>
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
        <Tabs v-model="activeTab" class="w-auto">
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
              class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground"
            />
            <Input
              v-model="searchQuery"
              placeholder="Search endpoints..."
              class="pl-10 pr-4 py-2.5 w-full"
            />
          </div>
          <Button @click="showCreateEndpointModal = true">
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
          <div class="w-full border-t border-border"></div>
        </div>
        <div class="relative flex justify-center body-sm">
          <span class="px-4 bg-background text-muted-foreground font-medium">
            Demo: Empty State (shown when no endpoints exist)
          </span>
        </div>
      </div>

      <!-- Empty state content -->
      <div class="mt-8 bg-card rounded-lg shadow border border-border p-8">
        <div class="text-center py-12">
          <div
            class="mx-auto w-14 h-14 bg-muted rounded-full flex items-center justify-center mb-6"
          >
            <Server class="w-7 h-7 text-muted-foreground" />
          </div>
          <h3 class="heading-2 text-foreground mb-3">No endpoints yet</h3>
          <p class="body-sm text-muted-foreground mb-8 max-w-sm mx-auto">
            Get started by creating your first endpoint to share data or models.
          </p>
          <div class="flex items-center justify-center gap-3">
            <Button @click="showCreateEndpointModal = true">
              <Plus class="h-4 w-4 mr-2" />
              Create your first endpoint
            </Button>
            <Button variant="outline"> Learn more </Button>
          </div>
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
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
