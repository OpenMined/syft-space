<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center">
          <Button 
            variant="ghost"
            @click="router.push({ name: 'endpoints' })"
            class="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft class="w-5 h-5 mr-2" />
            Back to Endpoints
          </Button>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-6 py-12">
      <!-- Main heading -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-gray-900 mb-4 text-balance">
          What type of endpoint do you want to create?
        </h1>
      </div>

      <!-- Endpoint type cards -->
      <div class="grid md:grid-cols-2 gap-8 mb-8">
        <!-- Data Endpoint Card -->
        <Card 
          class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white border-gray-200"
          @click="selectEndpointType('data')"
        >
          <CardContent class="p-8">
            <div class="flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-6">
                <Database class="w-8 h-8 text-blue-600" />
              </div>
              
              <h3 class="text-2xl font-bold text-gray-900 mb-3">I have data</h3>
              <p class="text-sm font-medium mb-4 text-blue-600 dark:text-blue-400">Create a Data-as-a-Endpoint solution</p>

              <p class="text-gray-600 mb-4 text-balance">
                Transform your documents, PDFs, or vector databases into searchable API endpoints.
              </p>
              
              <p class="text-sm text-gray-500 mb-6 text-balance">
                Perfect for creating knowledge bases, document search, and domain-specific Q&A systems.
              </p>
            </div>
          </CardContent>
        </Card>

        <!-- Model Endpoint Card -->
        <Card 
          class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-purple-300 hover:bg-gradient-to-br hover:from-purple-50 hover:to-pink-50 border-2 bg-white border-gray-200"
          @click="selectEndpointType('model')"
        >
          <CardContent class="p-8">
            <div class="flex flex-col items-center text-center">
              <div class="w-16 h-16 rounded-full bg-purple-100 flex items-center justify-center mb-6">
                <Brain class="w-8 h-8 text-purple-600" />
              </div>
              
              <h3 class="text-2xl font-bold text-gray-900 mb-3">I have a model</h3>
              <p class="text-sm font-medium mb-4 text-purple-600 dark:text-purple-400">Create a Model-as-a-Endpoint solution</p>

              <p class="text-gray-600 mb-4 text-balance">
                Deploy your fine-tuned or general-purpose AI models as accessible API endpoints.
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
import { useRouter } from 'vue-router'
import { Database, Brain, Shield, ArrowLeft } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const router = useRouter()

const selectEndpointType = (type: 'data' | 'model') => {
  if (type === 'data') {
    router.push({name: 'create-data-endpoint'})
  } else if (type === 'model') {
    router.push({name: 'create-model-endpoint'})
  }
}
</script>