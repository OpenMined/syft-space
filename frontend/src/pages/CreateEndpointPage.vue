<template>
  <div class="min-h-screen bg-white">
    <!-- Header (like GitHub's new repo flow) -->
    <div class="border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex items-center">
          <button
            @click="router.push({ name: 'endpoints' })"
            class="text-gray-500 hover:text-gray-700 transition-colors"
          >
            <ArrowLeft class="w-5 h-5" />
          </button>
          <span class="ml-4 text-sm text-gray-500">New endpoint</span>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
      <!-- Heading with context -->
      <div class="mb-8">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-semibold text-gray-900 mb-2">
              Share your first resource
            </h1>
            <p class="text-gray-500">
              Tell us about what you're sharing
            </p>
          </div>
        </div>
      </div>

      <!-- Option Cards with guidance -->
      <div class="space-y-4 mb-8">
        <!-- Help text for different personas -->
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
          <h4 class="font-medium text-amber-900 mb-3">💡 Not sure which to choose?</h4>
          <div class="space-y-2 text-sm text-amber-800">
            <div class="flex items-start gap-2">
              <span class="text-amber-600">•</span>
              <span><strong>Do you have files to add?</strong> (PDFs, CSVs, documents) → Choose <strong>Documents & Data</strong></span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-amber-600">•</span>
              <span><strong>Do you want to bring your own specialized AI model?</strong> → Choose <strong>AI Models</strong></span>
            </div>
          </div>
        </div>
        <!-- Data Option -->
        <button
          @click="selectEndpointType('data')"
          class="w-full p-6 bg-white border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50/50 transition-all text-left group"
        >
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-blue-200 transition-colors">
              <Database class="w-6 h-6 text-blue-600" />
            </div>
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <h3 class="text-lg font-semibold text-gray-900">Documents & Data</h3>
                <div class="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                  </svg>
                  ~2 mins setup
                </div>
              </div>
              <p class="text-sm text-gray-600 mb-3">
                Share PDFs, CSVs, documents, or connect to databases. Make your content searchable and queryable.
              </p>
              <div class="mb-3">
                <p class="text-xs text-gray-500 mb-2">Popular for:</p>
                <div class="flex flex-wrap gap-2">
                  <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">News archives</span>
                  <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">Research papers</span>
                  <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">Books & reports</span>
                  <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">Lab data</span>
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">PDF</span>
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">CSV</span>
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">Markdown</span>
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">Database</span>
              </div>
            </div>
            <ChevronRight class="w-5 h-5 text-gray-400 group-hover:text-blue-600 transition-colors" />
          </div>
        </button>

        <!-- Model Option -->
        <button
          @click="selectEndpointType('model')"
          class="w-full p-6 bg-white border-2 border-gray-200 rounded-lg hover:border-purple-500 hover:bg-purple-50/50 transition-all text-left group"
        >
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-purple-200 transition-colors">
              <Brain class="w-6 h-6 text-purple-600" />
            </div>
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <h3 class="text-lg font-semibold text-gray-900">AI Models</h3>
                <div class="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded-full">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
                  </svg>
                  ~10 mins setup
                </div>
              </div>
              <p class="text-sm text-gray-600 mb-3">
                Bring your existing models or quickly set up a local one. A great choice for sharing your model or simply setting up a complete AI workflow on your machine.</p>
              <div class="mb-3">
                <p class="text-xs text-gray-500 mb-2">Popular for:</p>
                <div class="flex flex-wrap gap-2">
                  <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">Specialized LLMs</span>
                  <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">Local LLMs</span>
                  <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">Custom AI workflows</span>
                  <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">Third-party LLMs</span>
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">vLLM</span>
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">Ollama</span>
                <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">Custom</span>
              </div>
            </div>
            <ChevronRight class="w-5 h-5 text-gray-400 group-hover:text-purple-600 transition-colors" />
          </div>
        </button>
      </div>

      <!-- Info Box (like Stripe's security notice) -->
      <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div class="flex items-start gap-3">
          <Shield class="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
          <div class="text-sm text-gray-600">
            <p class="font-medium text-gray-900 mb-1">Your data never leaves your system</p>
            <p>All content remains on your infrastructure. You maintain complete control over access permissions and can review every request before approval.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Database, Brain, Shield, ArrowLeft, ChevronRight } from 'lucide-vue-next'

const router = useRouter()

const selectEndpointType = (type: 'data' | 'model') => {
  if (type === 'data') {
    router.push({ name: 'create-data-endpoint' })
  } else if (type === 'model') {
    router.push({ name: 'create-model-endpoint' })
  }
}
</script>
