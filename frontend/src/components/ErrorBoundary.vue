<template>
  <div v-if="hasError" class="error-boundary">
    <div
      class="bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-lg p-6"
    >
      <div class="flex items-start">
        <AlertCircle class="h-5 w-5 text-red-400 dark:text-red-500 mt-0.5 mr-3 flex-shrink-0" />
        <div class="flex-1">
          <h3 class="text-sm font-medium text-red-800 dark:text-red-200 mb-1">
            {{ errorTitle }}
          </h3>
          <p class="text-sm text-red-700 dark:text-red-300 mb-4">
            {{ errorMessage }}
          </p>

          <!-- Error details (only in development) -->
          <details v-if="showDetails && errorDetails" class="mb-4">
            <summary
              class="text-xs text-red-600 dark:text-red-400 cursor-pointer hover:text-red-800 dark:hover:text-red-200"
            >
              Show technical details
            </summary>
            <pre
              class="mt-2 text-xs text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-950/30 p-2 rounded overflow-auto font-mono"
              >{{ errorDetails }}</pre
            >
          </details>

          <div class="flex flex-wrap gap-2">
            <Button
              v-if="canRetry"
              @click="handleRetry"
              size="sm"
              variant="outline"
              class="text-red-700 dark:text-red-300 border-red-300 dark:border-red-700 hover:bg-red-100 dark:hover:bg-red-950/30"
            >
              <RefreshCw class="h-3 w-3 mr-1" />
              Try Again
            </Button>

            <Button
              @click="handleDismiss"
              size="sm"
              variant="ghost"
              class="text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-950/30"
            >
              Dismiss
            </Button>

            <Button
              v-if="fallbackAction"
              @click="fallbackAction.handler"
              size="sm"
              variant="outline"
              class="text-red-700 dark:text-red-300 border-red-300 dark:border-red-700 hover:bg-red-100 dark:hover:bg-red-950/30"
            >
              {{ fallbackAction.label }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <slot v-else />
</template>

<script setup lang="ts">
import { computed, onErrorCaptured, ref } from 'vue'
import { AlertCircle, RefreshCw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useErrorHandling } from '@/composables/useErrorHandling'

interface FallbackAction {
  label: string
  handler: () => void
}

interface Props {
  canRetry?: boolean
  showDetails?: boolean
  fallbackAction?: FallbackAction
  customTitle?: string
  customMessage?: string
}

interface Emits {
  (e: 'error', error: Error): void
  (e: 'retry'): void
  (e: 'dismiss'): void
}

const props = withDefaults(defineProps<Props>(), {
  canRetry: true,
  showDetails: import.meta.env.DEV,
})

const emit = defineEmits<Emits>()

const { handleApiError, getErrorMessage } = useErrorHandling()

const error = ref<Error | null>(null)
const errorInfo = ref<string>('')

// Capture errors in child components
onErrorCaptured((err: Error, instance, info) => {
  error.value = err
  errorInfo.value = info
  emit('error', err)

  // Return false to prevent the error from propagating further
  return false
})

// Computed properties
const hasError = computed(() => error.value !== null)

const errorTitle = computed(() => {
  if (props.customTitle) return props.customTitle

  if (!error.value) return ''

  // Determine error type based on error characteristics
  if (error.value.name === 'ValidationError') return 'Validation Error'
  if (error.value.name === 'NetworkError') return 'Connection Error'
  if (error.value.message?.includes('fetch')) return 'Network Error'

  return 'Something went wrong'
})

const errorMessage = computed(() => {
  if (props.customMessage) return props.customMessage

  if (!error.value) return ''

  // Convert error to our standardized format
  const errorState = handleApiError(error.value)
  return getErrorMessage(errorState)
})

const errorDetails = computed(() => {
  if (!error.value) return ''

  return JSON.stringify(
    {
      name: error.value.name,
      message: error.value.message,
      stack: error.value.stack,
      componentInfo: errorInfo.value,
    },
    null,
    2,
  )
})

// Event handlers
const handleRetry = () => {
  error.value = null
  errorInfo.value = ''
  emit('retry')
}

const handleDismiss = () => {
  error.value = null
  errorInfo.value = ''
  emit('dismiss')
}

// Expose error state for parent components
defineExpose({
  hasError,
  error,
  clearError: () => {
    error.value = null
    errorInfo.value = ''
  },
})
</script>

<style scoped>
.error-boundary {
  margin: 1rem 0;
}

details summary {
  user-select: none;
}

pre {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
