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
          <p class="body-lg text-muted-foreground md:max-w-[60%]">
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

    <!-- Loading state -->
    <div v-if="endpointsStore.isLoading" class="flex justify-center py-12">
      <div class="flex items-center gap-3">
        <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
        <span class="text-muted-foreground">Loading endpoints...</span>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="endpointsStore.error" class="text-center py-8">
      <div class="bg-destructive/10 text-destructive rounded-lg p-4 max-w-md mx-auto">
        <p class="font-medium">Failed to load endpoints</p>
        <p class="text-sm mt-1">{{ endpointsStore.error }}</p>
        <Button variant="outline" size="sm" class="mt-3" @click="endpointsStore.fetchEndpoints()">
          Try again
        </Button>
      </div>
    </div>

    <!-- Endpoint cards -->
    <div v-else-if="filteredEndpoints.length > 0" class="space-y-5">
      <EndpointCard
        v-for="endpoint in filteredEndpoints"
        :key="endpoint.id"
        :endpoint="endpoint"
        @delete="handleDeleteEndpoint"
      />
    </div>

    <!-- No results state -->
    <div v-else-if="!endpointsStore.isLoading && searchQuery" class="text-center py-12">
      <p class="text-muted-foreground">No endpoints found matching "{{ searchQuery }}"</p>
    </div>

    <!-- DEMO: Empty State Section -->
    <div
      v-if="
        !endpointsStore.isLoading &&
        !endpointsStore.error &&
        endpointsStore.endpoints.length === 0 &&
        !searchQuery
      "
      class="mt-16"
    >
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

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[600px]">
      <div class="space-y-4">
        <div>
          <h3 class="body-sm font-semibold text-destructive">Danger Zone</h3>
          <p class="body-sm text-muted-foreground mt-1">
            Permanently delete this endpoint and all associated data.
          </p>
        </div>
        <DialogHeader>
          <DialogTitle>Delete endpoint</DialogTitle>
          <DialogDescription>
            This action cannot be undone. Please type
            <span class="font-medium text-foreground"> {{ endpointToDelete?.name }} </span>
            to confirm deletion.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-2">
          <Label class="body-sm text-muted-foreground">Confirm name</Label>
          <Input
            v-model="deleteNameConfirm"
            :placeholder="endpointToDelete?.name || 'endpoint-name'"
          />
          <p
            class="body-sm"
            :class="
              deleteNameConfirm === endpointToDelete?.name
                ? 'text-success'
                : 'text-muted-foreground'
            "
          >
            {{
              deleteNameConfirm === endpointToDelete?.name
                ? 'Name matches'
                : 'Enter the endpoint name exactly'
            }}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="cancelDeleteEndpoint" :disabled="isDeleting">Cancel</Button>
          <Button
            variant="destructive"
            :disabled="deleteNameConfirm !== endpointToDelete?.name || isDeleting"
            @click="confirmDeleteEndpoint"
          >
            <div v-if="isDeleting" class="flex items-center gap-2">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              Deleting...
            </div>
            <span v-else>Delete Endpoint</span>
          </Button>
        </DialogFooter>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Plus, Server, HelpCircle } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import EndpointCard from '@/components/EndpointCard.vue'
import CreateEndpointModal from '@/components/CreateEndpointModal.vue'
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'
import { endpointsApi } from '@/api/endpoints/endpoints'

const endpointsStore = useEndpointsStore()

// Fetch endpoints on mount
onMounted(() => {
  endpointsStore.fetchEndpoints()
})

const searchQuery = ref('')
const activeTab = ref('all')
const showCreateEndpointModal = ref(false)
const showDeleteDialog = ref(false)
const endpointToDelete = ref<EndpointItem | null>(null)
const deleteNameConfirm = ref('')
const isDeleting = ref(false)

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
    if (activeTab.value === 'published' && !endpoint.published) {
      return false
    }
    if (activeTab.value === 'draft' && endpoint.published) {
      return false
    }

    return true
  })
})

const handleDeleteEndpoint = (endpoint: EndpointItem) => {
  endpointToDelete.value = endpoint
  deleteNameConfirm.value = ''
  showDeleteDialog.value = true
}

const cancelDeleteEndpoint = () => {
  showDeleteDialog.value = false
  endpointToDelete.value = null
  deleteNameConfirm.value = ''
}

const confirmDeleteEndpoint = async () => {
  if (endpointToDelete.value && !isDeleting.value) {
    isDeleting.value = true
    
    try {
      if (!endpointToDelete.value.slug) {
        throw new Error('Endpoint slug is undefined')
      }
      
      // Call the delete API
      await endpointsApi.delete(endpointToDelete.value.slug)

      // Remove from store after successful deletion
      const index = endpointsStore.endpoints.findIndex((e) => e.id === endpointToDelete.value!.id)
      if (index > -1) {
        endpointsStore.endpoints.splice(index, 1)
      }

      // Reset dialog state
      showDeleteDialog.value = false
      endpointToDelete.value = null
      deleteNameConfirm.value = ''
    } catch (error) {
      console.error('Failed to delete endpoint:', error)
      // You might want to show an error toast here
      // For now, just log the error and close the dialog
    } finally {
      isDeleting.value = false
    }
  }
}
</script>
