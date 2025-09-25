<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <Settings class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Settings</h1>
    </div>
    <p class="text-gray-600 mb-8">Manage your data sources, policies, and server configurations</p>

    <!-- Tabs -->
    <Tabs default-value="general" class="w-full">
      <TabsList
        class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-4 lg:w-[500px] mb-8"
      >
        <TabsTrigger value="general">General</TabsTrigger>
        <TabsTrigger value="data-sources">Data Sources</TabsTrigger>
        <TabsTrigger value="models">Models</TabsTrigger>
        <TabsTrigger value="policies">Policies</TabsTrigger>
      </TabsList>

      <TabsContent value="general" class="space-y-6">
        <!-- Wallet Manager Section -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <div class="flex items-center gap-3 mb-6">
            <div class="p-2 bg-purple-100 rounded-md">
              <Shield class="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <h3 class="text-lg font-medium text-gray-900">Wallet Manager</h3>
              <p class="text-sm text-gray-600">
                Configure your wallet management settings and authentication
              </p>
            </div>
          </div>

          <!-- Warning Alert -->
          <div class="bg-yellow-50 border border-yellow-200 rounded-md p-4 mb-6">
            <div class="flex items-start gap-3">
              <AlertCircle class="h-5 w-5 text-yellow-600 mt-0.5" />
              <p class="text-sm text-yellow-800">
                Please ensure you fully trust this wallet manager as it handles financial
                transactions
              </p>
            </div>
          </div>

          <!-- Form Fields -->
          <div class="space-y-6">
            <!-- Manager URL -->
            <div class="space-y-2">
              <Label for="manager-url" class="text-sm font-medium text-gray-700">Manager URL</Label>
              <div class="relative">
                <Input
                  id="manager-url"
                  type="url"
                  v-model="userStore.walletManagerUrl"
                  placeholder="https://payments.openmined.org"
                  class="pr-10"
                />
                <Copy
                  class="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 cursor-pointer hover:text-gray-600"
                />
              </div>
            </div>

            <!-- Email Address -->
            <div class="space-y-2">
              <Label for="email" class="text-sm font-medium text-gray-700">Email Address</Label>
              <Input
                id="email"
                type="email"
                v-model="userStore.email"
                placeholder="Enter your email address"
              />
            </div>

            <!-- Auth Token -->
            <div class="space-y-2">
              <Label for="auth-token" class="text-sm font-medium text-gray-700">Auth Token</Label>
              <Input
                id="auth-token"
                type="password"
                v-model="userStore.authToken"
                placeholder="Enter your authentication token"
              />
            </div>
          </div>
        </div>

        <!-- Save Button -->
        <div class="mt-8 flex justify-end">
          <Button class="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2">
            Save Changes
          </Button>
        </div>
      </TabsContent>

      <TabsContent value="data-sources" class="space-y-6">
        <!-- Data Sources Header -->
        <div class="flex items-center justify-between mb-8">
          <div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">Data Sources</h3>
            <p class="text-gray-600">Manage your connected data sources and vector databases</p>
          </div>
          <Button
            class="bg-purple-600 hover:bg-purple-700 text-white"
            @click="showCreateDataSourceDialog = true"
          >
            <Plus class="h-4 w-4 mr-2" />
            Add Data Source
          </Button>
        </div>

        <!-- Data Sources List -->
        <div class="space-y-4">

          <!-- Legal Documents Store -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="p-3 bg-purple-100 rounded-lg">
                  <IntegrationIcon name="weaviate" class="h-6 w-6" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">Legal Documents Store</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1"
                      >Weaviate</Badge
                    >
                    <Badge
                      variant="outline"
                      class="bg-green-50 text-green-700 border-green-200 text-xs px-2 py-1"
                    >
                      <div class="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                      running
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">
                    Vector database for legal document analysis and retrieval
                  </p>
                  <div class="flex gap-2">
                    <Badge variant="outline" class="text-xs px-2 py-1">legal</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">documents</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">analysis</Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>

          <!-- Customer Analytics Store -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="p-3 bg-blue-100 rounded-lg">
                  <IntegrationIcon name="qdrant" class="h-6 w-6" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">Customer Analytics Store</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1"
                      >Qdrant</Badge
                    >
                    <Badge
                      variant="outline"
                      class="bg-green-50 text-green-700 border-green-200 text-xs px-2 py-1"
                    >
                      <div class="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                      running
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">
                    Vector database for customer behavior analysis and segmentation
                  </p>
                  <div class="flex gap-2">
                    <Badge variant="outline" class="text-xs px-2 py-1">customer</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">analytics</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">segmentation</Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>

          <!-- Research Database -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="p-3 bg-green-100 rounded-lg">
                  <IntegrationIcon name="chroma" class="h-6 w-6" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">Research Database</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1"
                      >Chroma</Badge
                    >
                    <Badge
                      variant="outline"
                      class="bg-gray-50 text-gray-600 border-gray-200 text-xs px-2 py-1"
                    >
                      <div class="w-2 h-2 bg-gray-400 rounded-full mr-1"></div>
                      stopped
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">
                    Knowledge base for research papers and scientific literature
                  </p>
                  <div class="flex gap-2">
                    <Badge variant="outline" class="text-xs px-2 py-1">research</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">papers</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">knowledge</Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="models" class="space-y-6">
        <!-- Models Header -->
        <div class="flex items-center justify-between mb-8">
          <div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">AI Models</h3>
            <p class="text-gray-600">Configure your AI models and inference engines</p>
          </div>
          <Button
            class="bg-purple-600 hover:bg-purple-700 text-white"
            @click="showCreateModelDialog = true"
          >
            <Plus class="h-4 w-4 mr-2" />
            Add Model
          </Button>
        </div>

        <!-- Models List -->
        <div class="space-y-4">

          <!-- NLP Processing Engine -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="p-3 bg-purple-100 rounded-lg">
                  <IntegrationIcon name="vllm" class="h-6 w-6" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">NLP Processing Engine</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1"
                      >vLLM</Badge
                    >
                    <Badge
                      variant="outline"
                      class="bg-gray-50 text-gray-600 border-gray-200 text-xs px-2 py-1"
                    >
                      <div class="w-2 h-2 bg-gray-400 rounded-full mr-1"></div>
                      stopped
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">
                    Large language model for natural language processing tasks
                  </p>
                  <div class="flex gap-2">
                    <Badge variant="outline" class="text-xs px-2 py-1">nlp</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">analysis</Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>

          <!-- Code Assistant Model -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="p-3 bg-orange-100 rounded-lg">
                  <IntegrationIcon name="ollama" class="h-6 w-6" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">Code Assistant Model</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1"
                      >Ollama</Badge
                    >
                    <Badge
                      variant="outline"
                      class="bg-green-50 text-green-700 border-green-200 text-xs px-2 py-1"
                    >
                      <div class="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                      running
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">
                    Local code generation and programming assistance model
                  </p>
                  <div class="flex gap-2">
                    <Badge variant="outline" class="text-xs px-2 py-1">code</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">programming</Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>

          <!-- Text Embedding Service -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="p-3 bg-indigo-100 rounded-lg">
                  <IntegrationIcon name="huggingface" class="h-6 w-6" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">Text Embedding Service</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1"
                      >Hugging Face</Badge
                    >
                    <Badge
                      variant="outline"
                      class="bg-gray-50 text-gray-600 border-gray-200 text-xs px-2 py-1"
                    >
                      <div class="w-2 h-2 bg-gray-400 rounded-full mr-1"></div>
                      stopped
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">
                    High-quality text embeddings for semantic search and similarity
                  </p>
                  <div class="flex gap-2">
                    <Badge variant="outline" class="text-xs px-2 py-1">embeddings</Badge>
                    <Badge variant="outline" class="text-xs px-2 py-1">semantic</Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="policies" class="space-y-6">
        <!-- Policies Header -->
        <div class="flex items-center justify-between mb-8">
          <div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">Policy Configuration</h3>
            <p class="text-gray-600">
              Add and configure policies for your services
            </p>
          </div>
          <Button
            class="bg-purple-600 hover:bg-purple-700 text-white"
            @click="showCreatePolicyDialog = true"
          >
            <Plus class="h-4 w-4 mr-2" />
            Create Policy
          </Button>
        </div>

        <!-- Active Policies -->
        <div class="space-y-4">
          <div class="flex items-center gap-3 mb-4">
            <h4 class="text-lg font-semibold text-gray-900">Active Policies</h4>
            <Badge variant="secondary" class="bg-gray-100 text-gray-700 text-xs px-2 py-1">{{ activePolicies.length }}</Badge>
          </div>

          <div
            v-for="policy in activePolicies"
            :key="policy.id"
            class="bg-white border border-gray-200 rounded-lg p-6"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div :class="{
                  'p-3 rounded-lg bg-blue-100': policy.color === 'blue',
                  'p-3 rounded-lg bg-green-100': policy.color === 'green',
                  'p-3 rounded-lg bg-purple-100': policy.color === 'purple',
                  'p-3 rounded-lg bg-red-100': policy.color === 'red',
                  'p-3 rounded-lg bg-orange-100': policy.color === 'orange'
                }">
                  <component :is="policy.icon" :class="{
                    'h-6 w-6 text-blue-600': policy.color === 'blue',
                    'h-6 w-6 text-green-600': policy.color === 'green',
                    'h-6 w-6 text-purple-600': policy.color === 'purple',
                    'h-6 w-6 text-red-600': policy.color === 'red',
                    'h-6 w-6 text-orange-600': policy.color === 'orange'
                  }" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">{{ policy.name }}</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1">{{ policy.badge }}</Badge>
                    <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs px-2 py-1">
                      <div class="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                      {{ policy.serviceCount }} services
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">{{ policy.description }}</p>
                  <div class="flex gap-2">
                    <Badge
                      v-for="config in policy.configs"
                      :key="config"
                      variant="outline"
                      class="text-xs px-2 py-1"
                    >
                      {{ config }}
                    </Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>

        </div>

        <!-- Inactive Policies -->
        <div class="space-y-4 mt-8">
          <div class="flex items-center gap-3 mb-4">
            <h4 class="text-lg font-semibold text-gray-900">Inactive Policies</h4>
            <Badge variant="secondary" class="bg-gray-100 text-gray-700 text-xs px-2 py-1">{{ inactivePolicies.length }}</Badge>
          </div>

          <div
            v-for="policy in inactivePolicies"
            :key="policy.id"
            class="bg-white border border-gray-200 rounded-lg p-6"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div :class="{
                  'p-3 rounded-lg bg-blue-100': policy.color === 'blue',
                  'p-3 rounded-lg bg-green-100': policy.color === 'green',
                  'p-3 rounded-lg bg-purple-100': policy.color === 'purple',
                  'p-3 rounded-lg bg-red-100': policy.color === 'red',
                  'p-3 rounded-lg bg-orange-100': policy.color === 'orange'
                }">
                  <component :is="policy.icon" :class="{
                    'h-6 w-6 text-blue-600': policy.color === 'blue',
                    'h-6 w-6 text-green-600': policy.color === 'green',
                    'h-6 w-6 text-purple-600': policy.color === 'purple',
                    'h-6 w-6 text-red-600': policy.color === 'red',
                    'h-6 w-6 text-orange-600': policy.color === 'orange'
                  }" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <h3 class="text-lg font-medium text-gray-900">{{ policy.name }}</h3>
                    <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1">{{ policy.badge }}</Badge>
                    <Badge variant="outline" class="bg-gray-50 text-gray-600 border-gray-200 text-xs px-2 py-1">
                      <div class="w-2 h-2 bg-gray-400 rounded-full mr-1"></div>
                      Inactive
                    </Badge>
                  </div>
                  <p class="text-gray-600 mb-3">{{ policy.description }}</p>
                  <div class="flex gap-2">
                    <Badge
                      v-for="config in policy.configs"
                      :key="config"
                      variant="outline"
                      class="text-xs px-2 py-1"
                    >
                      {{ config }}
                    </Badge>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Button variant="outline" size="sm" class="text-gray-600">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit
                </Button>
                <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>
          </div>
        </div>
      </TabsContent>
    </Tabs>
  </div>

  <!-- Create Data Source Dialog -->
  <CreateDataSourceDialog
    v-model:open="showCreateDataSourceDialog"
    @data-source-created="handleDataSourceCreated"
  />

  <!-- Create Model Dialog -->
  <CreateModelDialog
    v-model:open="showCreateModelDialog"
    @model-created="handleModelCreated"
  />

  <!-- Create Policy Dialog -->
  <CreatePolicyDialog v-model:open="showCreatePolicyDialog" @policy-created="handlePolicyCreated" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  Settings,
  Shield,
  AlertCircle,
  Copy,
  Plus,
  Database,
  Brain,
  Edit,
  Trash2,
  Gauge,
  Calculator,
  Activity,
  Users,
} from 'lucide-vue-next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useUserStore } from '@/stores/user'
import CreateDataSourceDialog from '@/components/CreateDataSourceDialog.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import CreatePolicyDialog from '@/components/CreatePolicyDialog.vue'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import { getActivePolicies, getInactivePolicies } from '@/data/policies'

const userStore = useUserStore()
const showCreateDataSourceDialog = ref(false)
const showCreateModelDialog = ref(false)
const showCreatePolicyDialog = ref(false)

// Get policies from shared data
const activePolicies = getActivePolicies()
const inactivePolicies = getInactivePolicies()

const handleDataSourceCreated = () => {
  console.log('Data source created successfully')
}

const handleModelCreated = () => {
  console.log('Model created successfully')
}

const handlePolicyCreated = () => {
  console.log('Policy created successfully')
}
</script>
