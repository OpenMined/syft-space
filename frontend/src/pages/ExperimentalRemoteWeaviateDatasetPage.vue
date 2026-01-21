<template>
  <div class="min-h-screen">
    <!-- Main Content -->
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Page Title -->
      <div class="mb-8">
        <div class="flex items-center justify-between">
          <h1 class="heading-1 text-foreground">Create Remote Weaviate Dataset</h1>
          <Badge variant="outline" class="text-orange-600 border-orange-300">
            Experimental
          </Badge>
        </div>
        <p class="text-muted-foreground mt-2">
          Connect to an existing Weaviate instance to use as a data source for your endpoints.
        </p>
      </div>

      <!-- Form Card -->
      <Card class="bg-card border-border">
        <CardContent class="p-6 space-y-8">
          <!-- Basic Information Section -->
          <div class="space-y-6">
            <div class="flex items-center gap-2 mb-4">
              <Database class="w-5 h-5 text-primary" />
              <h2 class="heading-3 text-foreground">Basic Information</h2>
            </div>

            <!-- Dataset Name -->
            <div class="space-y-2">
              <Label for="dataset-name" class="text-sm font-medium">
                Dataset Name <span class="text-red-500">*</span>
              </Label>
              <Input
                id="dataset-name"
                v-model="formData.name"
                placeholder="e.g., bbc-news-dataset"
                class="w-full font-mono"
              />
              <p class="text-sm text-muted-foreground">
                A unique identifier for this dataset. Use lowercase letters, numbers, and hyphens.
              </p>
            </div>

            <!-- Summary -->
            <div class="space-y-2">
              <Label for="summary" class="text-sm font-medium">Summary</Label>
              <Input
                id="summary"
                v-model="formData.summary"
                placeholder="e.g., BBC News articles for RAG testing"
                class="w-full"
              />
              <p class="text-sm text-muted-foreground">
                A brief description of what this dataset contains.
              </p>
            </div>

            <!-- Tags -->
            <div class="space-y-2">
              <Label for="tags" class="text-sm font-medium">Tags</Label>
              <div class="space-y-2">
                <div class="flex gap-2">
                  <Input
                    id="tags"
                    v-model="tagInput"
                    @keydown.enter.prevent="addTag"
                    placeholder="Add keywords like: news, articles, research"
                    class="flex-1"
                  />
                  <Button @click="addTag" variant="outline" :disabled="!tagInput.trim()">
                    <Plus class="h-4 w-4" />
                  </Button>
                </div>
                <p class="text-sm text-muted-foreground">Tags help organize and discover datasets.</p>

                <!-- Popular Tags Suggestions -->
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xs text-muted-foreground">Popular:</span>
                  <Button
                    v-for="suggestion in popularTags"
                    :key="suggestion"
                    @click="addSuggestedTag(suggestion)"
                    variant="ghost"
                    size="sm"
                    class="h-6 px-2 text-xs"
                    :disabled="formData.tags.includes(suggestion)"
                  >
                    {{ suggestion }}
                  </Button>
                </div>

                <!-- Selected Tags -->
                <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-3">
                  <Badge
                    v-for="(tag, index) in formData.tags"
                    :key="index"
                    variant="secondary"
                    class="px-3 py-1"
                  >
                    {{ tag }}
                    <button
                      @click="removeTag(index)"
                      class="ml-2 hover:text-destructive transition-colors"
                    >
                      <X class="h-3 w-3" />
                    </button>
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          <Separator />

          <!-- Weaviate Connection Section -->
          <div class="space-y-6">
            <div class="flex items-center gap-2 mb-4">
              <Server class="w-5 h-5 text-primary" />
              <h2 class="heading-3 text-foreground">Weaviate Connection</h2>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- HTTP URL -->
              <div class="space-y-2">
                <Label for="http-url" class="text-sm font-medium">
                  HTTP URL <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="http-url"
                  v-model="formData.configuration.http_url"
                  placeholder="http://localhost:9081"
                  class="w-full font-mono"
                />
              </div>

              <!-- gRPC URL -->
              <div class="space-y-2">
                <Label for="grpc-url" class="text-sm font-medium">
                  gRPC URL <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="grpc-url"
                  v-model="formData.configuration.grpc_url"
                  placeholder="http://localhost:9082"
                  class="w-full font-mono"
                />
              </div>
            </div>

            <!-- API Key -->
            <div class="space-y-2">
              <Label for="api-key" class="text-sm font-medium">
                API Key <span class="text-red-500">*</span>
              </Label>
              <Input
                id="api-key"
                v-model="formData.configuration.api_key"
                type="password"
                placeholder="Enter your Weaviate API key"
                class="w-full font-mono"
                autocomplete="new-password"
              />
              <p class="text-sm text-muted-foreground">
                The API key for authenticating with your Weaviate instance.
              </p>
            </div>

            <!-- Collection Name -->
            <div class="space-y-2">
              <Label for="collection-name" class="text-sm font-medium">
                Collection Name <span class="text-red-500">*</span>
              </Label>
              <Input
                id="collection-name"
                v-model="formData.configuration.collection_name"
                placeholder="e.g., BBCNews"
                class="w-full font-mono"
              />
              <p class="text-sm text-muted-foreground">
                The name of the Weaviate collection to connect to.
              </p>
            </div>
          </div>

          <Separator />

          <!-- Schema Configuration Section -->
          <div class="space-y-6">
            <div class="flex items-center gap-2 mb-4">
              <FileJson class="w-5 h-5 text-primary" />
              <h2 class="heading-3 text-foreground">Schema Configuration</h2>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- Content Property -->
              <div class="space-y-2">
                <Label for="content-property" class="text-sm font-medium">
                  Content Property <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="content-property"
                  v-model="formData.configuration.content_property"
                  placeholder="e.g., content"
                  class="w-full font-mono"
                />
                <p class="text-sm text-muted-foreground">
                  The property name containing the main text content.
                </p>
              </div>

              <!-- Similarity Threshold -->
              <div class="space-y-2">
                <Label for="similarity-threshold" class="text-sm font-medium">
                  Similarity Threshold
                </Label>
                <Input
                  id="similarity-threshold"
                  v-model.number="formData.configuration.default_similarity_threshold"
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  placeholder="0.5"
                  class="w-full font-mono"
                />
                <p class="text-sm text-muted-foreground">
                  Minimum similarity score (0.0 - 1.0). Default: 0.5
                </p>
              </div>
            </div>

            <!-- Metadata Properties -->
            <div class="space-y-2">
              <Label for="metadata-properties" class="text-sm font-medium">
                Metadata Properties
              </Label>
              <div class="space-y-2">
                <div class="flex gap-2">
                  <Input
                    id="metadata-properties"
                    v-model="metadataInput"
                    @keydown.enter.prevent="addMetadataProperty"
                    placeholder="Add property name (e.g., headline, author, url)"
                    class="flex-1 font-mono"
                  />
                  <Button
                    @click="addMetadataProperty"
                    variant="outline"
                    :disabled="!metadataInput.trim()"
                  >
                    <Plus class="h-4 w-4" />
                  </Button>
                </div>
                <p class="text-sm text-muted-foreground">
                  Additional properties to include in the metadata response.
                </p>

                <!-- Common Metadata Suggestions -->
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xs text-muted-foreground">Common:</span>
                  <Button
                    v-for="suggestion in commonMetadataProperties"
                    :key="suggestion"
                    @click="addSuggestedMetadataProperty(suggestion)"
                    variant="ghost"
                    size="sm"
                    class="h-6 px-2 text-xs font-mono"
                    :disabled="formData.configuration.metadata_properties.includes(suggestion)"
                  >
                    {{ suggestion }}
                  </Button>
                </div>

                <!-- Selected Metadata Properties -->
                <div
                  v-if="formData.configuration.metadata_properties.length > 0"
                  class="flex flex-wrap gap-2 mt-3"
                >
                  <Badge
                    v-for="(prop, index) in formData.configuration.metadata_properties"
                    :key="index"
                    variant="outline"
                    class="px-3 py-1 font-mono"
                  >
                    {{ prop }}
                    <button
                      @click="removeMetadataProperty(index)"
                      class="ml-2 hover:text-destructive transition-colors"
                    >
                      <X class="h-3 w-3" />
                    </button>
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          <Separator />

          <!-- JSON Preview -->
          <div class="space-y-4">
            <button
              @click="showJsonPreview = !showJsonPreview"
              class="flex items-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors"
            >
              <ChevronRight
                :class="['w-4 h-4 transition-transform', showJsonPreview ? 'rotate-90' : '']"
              />
              {{ showJsonPreview ? 'Hide' : 'Show' }} JSON Preview
            </button>

            <div
              v-if="showJsonPreview"
              class="bg-muted/50 border border-border rounded-lg p-4 overflow-auto"
            >
              <pre class="text-xs font-mono text-foreground whitespace-pre-wrap">{{
                jsonPreview
              }}</pre>
            </div>
          </div>

          <!-- Error Display -->
          <div
            v-if="creationError"
            class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg"
          >
            <div class="flex items-start gap-3">
              <AlertCircle class="w-5 h-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <div class="flex-1">
                <h4 class="font-medium text-red-900 dark:text-red-300 mb-1">
                  Failed to create dataset
                </h4>
                <p class="text-sm text-red-700 dark:text-red-400">{{ creationError }}</p>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex justify-end pt-4 border-t border-border">
            <Button @click="handleCreate" :disabled="!isFormValid || isCreating" class="px-8">
              <Loader2 v-if="isCreating" class="mr-2 h-4 w-4 animate-spin" />
              {{ isCreating ? 'Creating...' : 'Create Dataset' }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Database,
  Server,
  FileJson,
  Plus,
  X,
  ChevronRight,
  Loader2,
  AlertCircle,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'

const router = useRouter()

// Form state
const formData = ref({
  name: '',
  summary: '',
  tags: [] as string[],
  configuration: {
    http_url: '',
    grpc_url: '',
    api_key: '',
    collection_name: '',
    default_similarity_threshold: 0.5,
    content_property: '',
    metadata_properties: [] as string[],
  },
})

const tagInput = ref('')
const metadataInput = ref('')
const isCreating = ref(false)
const creationError = ref('')
const showJsonPreview = ref(false)

// Tag suggestions
const popularTags = ['news', 'articles', 'research', 'data', 'embeddings', 'rag']

// Common metadata property suggestions
const commonMetadataProperties = ['headline', 'author', 'url', 'title', 'date', 'source', 'topics']

// Computed
const isFormValid = computed(() => {
  const { name, configuration } = formData.value
  return (
    name.trim() !== '' &&
    configuration.http_url.trim() !== '' &&
    configuration.grpc_url.trim() !== '' &&
    configuration.api_key.trim() !== '' &&
    configuration.collection_name.trim() !== '' &&
    configuration.content_property.trim() !== ''
  )
})

const jsonPreview = computed(() => {
  const payload = {
    name: formData.value.name,
    dtype: 'remote_weaviate',
    summary: formData.value.summary,
    tags: formData.value.tags.join(','),
    configuration: {
      http_url: formData.value.configuration.http_url,
      grpc_url: formData.value.configuration.grpc_url,
      api_key: formData.value.configuration.api_key ? '***' : '',
      collection_name: formData.value.configuration.collection_name,
      default_similarity_threshold: formData.value.configuration.default_similarity_threshold,
      content_property: formData.value.configuration.content_property,
      metadata_properties:
        formData.value.configuration.metadata_properties.length > 0
          ? formData.value.configuration.metadata_properties
          : null,
    },
  }
  return JSON.stringify(payload, null, 2)
})

// Methods
const addTag = () => {
  const tag = tagInput.value.trim().toLowerCase()
  if (tag && !formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
    tagInput.value = ''
  }
}

const addSuggestedTag = (tag: string) => {
  if (!formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
  }
}

const removeTag = (index: number) => {
  formData.value.tags.splice(index, 1)
}

const addMetadataProperty = () => {
  const prop = metadataInput.value.trim()
  if (prop && !formData.value.configuration.metadata_properties.includes(prop)) {
    formData.value.configuration.metadata_properties.push(prop)
    metadataInput.value = ''
  }
}

const addSuggestedMetadataProperty = (prop: string) => {
  if (!formData.value.configuration.metadata_properties.includes(prop)) {
    formData.value.configuration.metadata_properties.push(prop)
  }
}

const removeMetadataProperty = (index: number) => {
  formData.value.configuration.metadata_properties.splice(index, 1)
}

const handleCreate = async () => {
  if (!isFormValid.value) return

  isCreating.value = true
  creationError.value = ''

  try {
    const payload = {
      name: formData.value.name.trim(),
      dtype: 'remote_weaviate',
      summary: formData.value.summary.trim(),
      tags: formData.value.tags.join(','),
      configuration: {
        http_url: formData.value.configuration.http_url.trim(),
        grpc_url: formData.value.configuration.grpc_url.trim(),
        api_key: formData.value.configuration.api_key.trim(),
        collection_name: formData.value.configuration.collection_name.trim(),
        default_similarity_threshold: formData.value.configuration.default_similarity_threshold,
        content_property: formData.value.configuration.content_property.trim(),
        metadata_properties:
          formData.value.configuration.metadata_properties.length > 0
            ? formData.value.configuration.metadata_properties
            : null,
      },
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await datasetsApi.create(payload as any)
    toast.success(`Dataset "${payload.name}" created successfully`)
    router.push({ name: 'dataset-detail', params: { slug: response.name } })
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
    creationError.value = errorMessage
    toast.error(`Failed to create dataset: ${errorMessage}`)
  } finally {
    isCreating.value = false
  }
}
</script>
