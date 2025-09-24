<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <Button 
            variant="ghost"
            @click="router.push({ name: 'services' })"
            class="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft class="w-5 h-5 mr-2" />
            Back to My Services
          </Button>
          <div class="text-sm font-medium text-blue-600 bg-blue-50 px-3 py-1 rounded-md">
            Step 1 of 3
          </div>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-6 py-12">
      <!-- Main heading -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-gray-900 mb-4 text-balance">
          What kind of service do you want to create?
        </h1>
      </div>

      <!-- Service type cards -->
      <div class="grid md:grid-cols-2 gap-8 mb-8">
        <!-- Data Service Card -->
        <Card 
          class="cursor-pointer transition-all duration-200 hover:shadow-lg border-2 bg-white"
          :class="selectedType === 'data' ? 'border-blue-300 shadow-lg bg-gradient-to-br from-blue-50 to-indigo-50' : 'border-gray-200 hover:border-gray-300'"
          @click="selectServiceType('data')"
        >
          <CardContent class="p-8">
            <div class="flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-6">
                <Database class="w-8 h-8 text-blue-600" />
              </div>
              
              <h3 class="text-2xl font-bold text-gray-900 mb-3">I have data</h3>
              <p class="text-sm font-medium mb-4 text-blue-600 dark:text-blue-400">Create a Data-as-a-Service solution</p>

              <p class="text-gray-600 mb-4 text-balance">
                Transform your documents, PDFs, or vector databases into searchable AI services.
              </p>
              
              <p class="text-sm text-gray-500 mb-6 text-balance">
                Perfect for creating knowledge bases, document search, and domain-specific Q&A systems.
              </p>
            </div>
          </CardContent>
        </Card>

        <!-- Model Service Card -->
        <Card 
          class="cursor-pointer transition-all duration-200 hover:shadow-lg border-2 bg-white"
          :class="selectedType === 'model' ? 'border-purple-300 shadow-lg bg-gradient-to-br from-purple-50 to-pink-50' : 'border-gray-200 hover:border-gray-300'"
          @click="selectServiceType('model')"
        >
          <CardContent class="p-8">
            <div class="flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-purple-100 flex items-center justify-center mb-6">
                <Brain class="w-8 h-8 text-purple-600" />
              </div>
              
              <h3 class="text-2xl font-bold text-gray-900 mb-3">I have a model</h3>
              <p class="text-sm font-medium mb-4 text-purple-600 dark:text-purple-400">Create a Model-as-a-Service solution</p>

              <p class="text-gray-600 mb-4 text-balance">
                Deploy your fine-tuned or general-purpose AI models as accessible services.
              </p>
              
              <p class="text-sm text-gray-500 mb-6 text-balance">
                Ideal for letting others interact with your model to get answers, predictions, or summaries.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- Disclaimer -->
      <div class="bg-blue-50 border border-blue-100 rounded-xl p-8">
        <div class="flex items-start space-x-4">
          <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
            <Shield class="w-4 h-4 text-blue-600" />
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">Your data and models never leave your system</h3>
            <p class="text-gray-600 text-sm">
              You stay in full control and can manually review or approve anything that is shared externally. All processing happens on your infrastructure securely.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Database, Brain, Shield, ArrowLeft } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const router = useRouter()
const selectedType = ref<string | null>(null)

const selectServiceType = (type: 'data' | 'model') => {
  selectedType.value = type
  // Navigate to the appropriate service creation flow
  // For now, we'll just log the selection
  console.log(`Selected service type: ${type}`)
  // TODO: Navigate to specific creation flows once they are implemented
}
</script>