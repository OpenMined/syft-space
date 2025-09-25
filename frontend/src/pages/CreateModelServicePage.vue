<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center">
          <Button 
            variant="ghost"
            @click="router.push('/create')"
            class="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft class="w-5 h-5 mr-2" />
            Back to Create Service
          </Button>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-6 py-12">
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-gray-900 mb-4">Configure Your Model Service</h1>
        <p class="text-lg text-gray-600">Set up your AI model and configure how it will be accessed</p>
      </div>

      <!-- Placeholder content -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div class="text-center text-gray-500">
          <Brain class="w-16 h-16 mx-auto mb-4 text-gray-400" />
          <p class="text-lg font-medium">Model Service Configuration</p>
          <p class="mt-2">This is where you'll configure your AI model, set parameters, and define access permissions.</p>
          <p class="mt-4 text-sm">Coming soon...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft, Brain } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const router = useRouter()
</script>