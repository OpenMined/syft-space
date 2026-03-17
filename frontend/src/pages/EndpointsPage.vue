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

    <!-- Actions Bar -->
    <div class="flex items-center justify-between mb-8">
      <div class="relative w-64">
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

    <!-- Loading state -->
    <div v-if="endpointsStore.isLoading" class="space-y-5">
      <div
        v-for="i in 3"
        :key="`skeleton-${i}`"
        class="bg-card border border-border rounded-xl p-6 animate-pulse"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 flex gap-4">
            <div class="w-14 h-14 bg-muted rounded-xl"></div>
            <div class="flex-1 space-y-2">
              <div class="h-6 bg-muted rounded w-1/3"></div>
              <div class="h-4 bg-muted rounded w-1/2"></div>
              <div class="h-4 bg-muted rounded w-2/3"></div>
            </div>
          </div>
        </div>
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
        @edit="handleEditEndpoint"
      />
    </div>

    <!-- No results state -->
    <div v-else-if="!endpointsStore.isLoading && searchQuery" class="text-center py-12">
      <p class="text-muted-foreground">No endpoints found matching "{{ searchQuery }}"</p>
    </div>

    <!-- Empty state -->
    <div
      v-if="
        !endpointsStore.isLoading &&
        !endpointsStore.error &&
        endpointsStore.endpoints.length === 0 &&
        !searchQuery
      "
      class="text-center py-8"
    >
      <Server class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">No endpoints yet</h3>
      <p class="body-sm text-muted-foreground mb-4">
        Get started by creating your first endpoint to share data or models.
      </p>
      <Button @click="showCreateEndpointModal = true">
        <Plus class="h-4 w-4 mr-2" />
        Create your first endpoint
      </Button>
    </div>
  </div>

  <!-- Create Endpoint Modal -->
  <CreateEndpointModal v-model:open="showCreateEndpointModal" />

  <!-- Edit Endpoint Dialog -->
  <EditEndpointDialog
    v-model:open="showEditDialog"
    :endpoint="endpointToEdit"
    @saved="handleEditSaved"
  />

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle class="text-destructive">Delete endpoint</DialogTitle>
        <DialogDescription>
          This will permanently delete this endpoint and remove it from SyftHub. This action cannot
          be undone.
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-2">
        <Label class="gap-1">
          Type <span class="font-semibold text-foreground">{{ endpointToDelete?.name }}</span> to
          confirm
        </Label>
        <Input
          v-model="deleteNameConfirm"
          :placeholder="endpointToDelete?.name || 'endpoint-name'"
        />
        <p
          v-if="deleteNameConfirm"
          class="text-sm"
          :class="
            deleteNameConfirm === endpointToDelete?.name ? 'text-success' : 'text-muted-foreground'
          "
        >
          {{
            deleteNameConfirm === endpointToDelete?.name ? 'Name matches' : 'Name does not match'
          }}
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="cancelDeleteEndpoint" :disabled="isDeleting">
          Cancel
        </Button>
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
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Plus, Server, HelpCircle } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
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
import EditEndpointDialog from '@/components/EditEndpointDialog.vue'
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { toast } from 'vue-sonner'

const endpointsStore = useEndpointsStore()

// Fetch endpoints on mount
onMounted(() => {
  endpointsStore.fetchEndpoints()
})

const searchQuery = ref('')
const showCreateEndpointModal = ref(false)
const showDeleteDialog = ref(false)
const endpointToDelete = ref<EndpointItem | null>(null)
const deleteNameConfirm = ref('')
const isDeleting = ref(false)

const showEditDialog = ref(false)
const endpointToEdit = ref<{ slug: string; name: string; summary: string } | null>(null)

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

    return true
  })
})

const handleDeleteEndpoint = (endpoint: EndpointItem) => {
  endpointToDelete.value = endpoint
  deleteNameConfirm.value = ''
  showDeleteDialog.value = true
}

const handleEditEndpoint = (endpoint: EndpointItem) => {
  endpointToEdit.value = {
    slug: endpoint.slug,
    name: endpoint.name,
    summary: endpoint.summary,
  }
  showEditDialog.value = true
}

const handleEditSaved = (data: { summary: string }) => {
  // Update the store
  if (endpointToEdit.value) {
    const index = endpointsStore.endpoints.findIndex((e) => e.slug === endpointToEdit.value!.slug)
    if (index > -1 && endpointsStore.endpoints[index]) {
      endpointsStore.endpoints[index].summary = data.summary
    }
  }
  endpointToEdit.value = null
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

      // Unpublish from SyftHub first if published
      if (endpointToDelete.value.published) {
        try {
          await endpointsApi.unpublish(endpointToDelete.value.slug)
        } catch (unpublishError) {
          console.error('Failed to unpublish endpoint:', unpublishError)
          toast.error('Failed to remove endpoint from SyftHub. Please try again.')
          isDeleting.value = false
          return
        }
      }

      // Call the delete API
      await endpointsApi.delete(endpointToDelete.value.slug)

      // Remove from store after successful deletion
      const index = endpointsStore.endpoints.findIndex((e) => e.id === endpointToDelete.value!.id)
      if (index > -1) {
        endpointsStore.endpoints.splice(index, 1)
      }

      toast.success('Endpoint deleted successfully')

      // Reset dialog state
      showDeleteDialog.value = false
      endpointToDelete.value = null
      deleteNameConfirm.value = ''
    } catch (error) {
      console.error('Failed to delete endpoint:', error)
      toast.error('Failed to delete endpoint. Please try again.')
    } finally {
      isDeleting.value = false
    }
  }
}
</script>
