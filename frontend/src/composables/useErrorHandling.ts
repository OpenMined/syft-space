/**
 * Composable for standardized error handling
 * Provides consistent error states and user feedback
 */

import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { ERROR_TYPES, HTTP_STATUS, APP_LIMITS, UI_CONSTANTS, type ValueOf } from '@/lib/constants'

export interface ErrorState {
  message: string
  type: ValueOf<typeof ERROR_TYPES>
  statusCode?: number
  details?: Record<string, unknown>
}

export interface AsyncOperation<T = unknown, TArgs extends unknown[] = unknown[]> {
  loading: Ref<boolean>
  error: Ref<ErrorState | null>
  data: Ref<T | null>
  execute: (...args: TArgs) => Promise<T>
  reset: () => void
}

export function useErrorHandling() {
  const globalError = ref<ErrorState | null>(null)
  const errorHistory = ref<ErrorState[]>([])

  // Error type helpers
  const createError = (
    message: string,
    type: ErrorState['type'] = ERROR_TYPES.UNKNOWN,
    statusCode?: number,
    details?: Record<string, unknown>
  ): ErrorState => ({
    message,
    type,
    statusCode,
    details
  })

  const handleApiError = (error: any): ErrorState => {
    if (error.response) {
      // API responded with error status
      const status = error.response.status
      const message = error.response.data?.message || error.message || 'An error occurred'
      
      let type: ErrorState['type'] = ERROR_TYPES.SERVER
      if (status >= HTTP_STATUS.CLIENT_ERROR_START && status < HTTP_STATUS.SERVER_ERROR_START) {
        type = status === HTTP_STATUS.UNPROCESSABLE_ENTITY ? ERROR_TYPES.VALIDATION : ERROR_TYPES.NETWORK
      }
      
      return createError(message, type, status, error.response.data)
    } else if (error.request) {
      // Network error
      return createError(
        'Network error. Please check your connection and try again.',
        ERROR_TYPES.NETWORK
      )
    } else {
      // Other error
      return createError(error.message || 'An unexpected error occurred')
    }
  }

  const setError = (error: ErrorState | string) => {
    const errorState = typeof error === 'string' 
      ? createError(error) 
      : error
      
    globalError.value = errorState
    errorHistory.value.unshift(errorState)
    
    // Keep only last N errors
    if (errorHistory.value.length > APP_LIMITS.MAX_ERROR_HISTORY_SIZE) {
      errorHistory.value = errorHistory.value.slice(0, APP_LIMITS.MAX_ERROR_HISTORY_SIZE)
    }
  }

  const clearError = () => {
    globalError.value = null
  }

  const clearErrorHistory = () => {
    errorHistory.value = []
  }

  // User-friendly error messages
  const getErrorMessage = (error: ErrorState): string => {
    switch (error.type) {
      case ERROR_TYPES.VALIDATION:
        return error.message || 'Please check your input and try again.'
      case ERROR_TYPES.NETWORK:
        return 'Connection error. Please check your internet and try again.'
      case ERROR_TYPES.SERVER:
        if (error.statusCode === HTTP_STATUS.INTERNAL_SERVER_ERROR) {
          return 'Server error. Please try again later.'
        }
        if (error.statusCode === HTTP_STATUS.FORBIDDEN) {
          return 'You do not have permission to perform this action.'
        }
        if (error.statusCode === HTTP_STATUS.NOT_FOUND) {
          return 'The requested resource was not found.'
        }
        return error.message || 'Server error occurred.'
      default:
        return error.message || 'An unexpected error occurred.'
    }
  }

  // Async operation wrapper
  const useAsyncOperation = <T = unknown, TArgs extends unknown[] = unknown[]>(
    operation: (...args: TArgs) => Promise<T>
  ): AsyncOperation<T, TArgs> => {
    const loading = ref(false)
    const error = ref<ErrorState | null>(null)
    const data = ref<T | null>(null)

    const execute = async (...args: TArgs): Promise<T> => {
      loading.value = true
      error.value = null
      
      try {
        const result = await operation(...args)
        data.value = result
        return result
      } catch (err) {
        const errorState = handleApiError(err)
        error.value = errorState
        setError(errorState)
        throw errorState
      } finally {
        loading.value = false
      }
    }

    const reset = () => {
      loading.value = false
      error.value = null
      data.value = null
    }

    return {
      loading,
      error,
      data,
      execute,
      reset
    }
  }

  // Retry logic
  const withRetry = async <T>(
    operation: () => Promise<T>,
    maxRetries: number = 3,
    delay: number = UI_CONSTANTS.DEFAULT_RETRY_DELAY
  ): Promise<T> => {
    let lastError: any
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation()
      } catch (error) {
        lastError = error
        
        if (attempt === maxRetries) {
          throw error
        }
        
        // Only retry on network errors or 5xx server errors
        const errorState = handleApiError(error)
        if (errorState.type === ERROR_TYPES.VALIDATION || 
            (errorState.statusCode && errorState.statusCode < HTTP_STATUS.SERVER_ERROR_START)) {
          throw error
        }
        
        // Exponential backoff
        const waitTime = delay * Math.pow(2, attempt - 1)
        await new Promise(resolve => setTimeout(resolve, waitTime))
      }
    }
    
    throw lastError
  }

  // Computed properties
  const hasError = computed(() => globalError.value !== null)
  const errorMessage = computed(() => 
    globalError.value ? getErrorMessage(globalError.value) : ''
  )

  return {
    // State
    globalError,
    errorHistory,
    
    // Computed
    hasError,
    errorMessage,
    
    // Methods
    createError,
    handleApiError,
    setError,
    clearError,
    clearErrorHistory,
    getErrorMessage,
    useAsyncOperation,
    withRetry
  }
}