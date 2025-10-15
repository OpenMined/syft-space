/**
 * Composable for Create Endpoint form logic
 * Handles common form state and operations for endpoint creation
 */

import { ref, computed, reactive } from 'vue'
import { APP_LIMITS, UI_CONSTANTS } from '@/lib/constants'
import type { Ref } from 'vue'

export interface EndpointFormData {
  name: string
  description: string
  summary?: string
  visibility: 'public' | 'private'
  tags: string[]
  pricing?: {
    type: 'free' | 'paid'
    amount?: string
    currency?: string
  }
}

export function useCreateEndpointForm() {
  // Form state
  const currentStep = ref(1)
  const isSubmitting = ref(false)
  const submitError = ref<string | null>(null)
  
  // Form data
  const formData = reactive<EndpointFormData>({
    name: '',
    description: '',
    summary: '',
    visibility: 'public',
    tags: [],
    pricing: {
      type: 'free'
    }
  })

  // Validation helpers
  const isValidStep = (step: number): boolean => {
    switch (step) {
      case 1: // Basic Info
        return !!(formData.name && formData.description)
      case 2: // Data Source / Model
        return true // Override in specific implementations
      case 3: // Output
        return true // Override in specific implementations  
      case 4: // Policies
        return true // Override in specific implementations
      case 5: // Review
        return isValidForm()
      default:
        return true
    }
  }

  const isValidForm = (): boolean => {
    return !!(
      formData.name &&
      formData.description &&
      formData.visibility
    )
  }

  // Navigation
  const canProceedToStep = (step: number): boolean => {
    for (let i = 1; i < step; i++) {
      if (!isValidStep(i)) return false
    }
    return true
  }

  const nextStep = () => {
    if (isValidStep(currentStep.value)) {
      currentStep.value++
    }
  }

  const previousStep = () => {
    if (currentStep.value > 1) {
      currentStep.value--
    }
  }

  const goToStep = (step: number) => {
    if (canProceedToStep(step)) {
      currentStep.value = step
    }
  }

  // Progress calculation
  const progress = computed(() => {
    return (currentStep.value / APP_LIMITS.TOTAL_ENDPOINT_CREATION_STEPS) * APP_LIMITS.PERCENTAGE_MULTIPLIER
  })

  // Save operations
  const saveDraft = async () => {
    try {
      // Implement save draft logic
      console.log('Saving draft...', formData)
      // In real app, this would call an API
      return true
    } catch (error) {
      console.error('Failed to save draft:', error)
      return false
    }
  }

  const submitForm = async () => {
    if (!isValidForm()) {
      submitError.value = 'Please fill in all required fields'
      return false
    }

    isSubmitting.value = true
    submitError.value = null

    try {
      // Implement form submission logic
      console.log('Submitting form...', formData)
      // In real app, this would call an API
      await new Promise(resolve => setTimeout(resolve, UI_CONSTANTS.API_SIMULATION_DELAY)) // Simulate API call
      return true
    } catch (error) {
      submitError.value = 'Failed to create endpoint. Please try again.'
      return false
    } finally {
      isSubmitting.value = false
    }
  }

  // Reset form
  const resetForm = () => {
    currentStep.value = 1
    isSubmitting.value = false
    submitError.value = null
    
    // Reset form data
    formData.name = ''
    formData.description = ''
    formData.summary = ''
    formData.visibility = 'public'
    formData.tags = []
    formData.pricing = { type: 'free' }
  }

  // Computed properties
  const isFirstStep = computed(() => currentStep.value === 1)
  const isLastStep = computed(() => currentStep.value === 5)
  const canSaveDraft = computed(() => !!formData.name)

  return {
    // State
    currentStep,
    isSubmitting,
    submitError,
    formData,
    
    // Computed
    progress,
    isFirstStep,
    isLastStep,
    canSaveDraft,
    
    // Validation
    isValidStep,
    isValidForm,
    canProceedToStep,
    
    // Navigation
    nextStep,
    previousStep,
    goToStep,
    
    // Operations
    saveDraft,
    submitForm,
    resetForm
  }
}