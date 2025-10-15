/**
 * Composable for multi-step form logic
 * Handles step navigation, validation, and state management
 */

import { ref, computed, reactive, readonly } from 'vue'

export interface FormStep {
  id: number
  title: string
  description?: string
  isValid?: () => boolean
}

export function useMultiStepForm(steps: FormStep[]) {
  const currentStep = ref(1)
  const formData = reactive<Record<string, unknown>>({})
  const errors = reactive<Record<string, string | null>>({})

  // Computed properties
  const isFirstStep = computed(() => currentStep.value === 1)
  const isLastStep = computed(() => currentStep.value === steps.length)
  const currentStepData = computed(() => steps.find((step) => step.id === currentStep.value))
  const canProceed = computed(() => {
    const step = currentStepData.value
    return step ? (step.isValid ? step.isValid() : true) : true
  })

  // Progress calculation
  const progress = computed(() => {
    return (currentStep.value / steps.length) * 100
  })

  // Navigation methods
  const nextStep = () => {
    if (!isLastStep.value && canProceed.value) {
      currentStep.value++
    }
  }

  const previousStep = () => {
    if (!isFirstStep.value) {
      currentStep.value--
    }
  }

  const goToStep = (stepNumber: number) => {
    if (stepNumber >= 1 && stepNumber <= steps.length) {
      currentStep.value = stepNumber
    }
  }

  // Validation methods
  const validateCurrentStep = (): boolean => {
    const step = currentStepData.value
    return step ? (step.isValid ? step.isValid() : true) : true
  }

  const validateAllSteps = (): boolean => {
    return steps.every((step) => (step.isValid ? step.isValid() : true))
  }

  // Utility methods
  const resetForm = () => {
    currentStep.value = 1
    Object.keys(formData).forEach((key) => {
      delete formData[key]
    })
    Object.keys(errors).forEach((key) => {
      delete errors[key]
    })
  }

  const setFieldValue = (field: string, value: unknown) => {
    formData[field] = value
    // Clear error when field is updated
    if (errors[field]) {
      delete errors[field]
    }
  }

  const setFieldError = (field: string, error: string) => {
    errors[field] = error
  }

  const clearFieldError = (field: string) => {
    if (errors[field]) {
      delete errors[field]
    }
  }

  return {
    // State
    currentStep: readonly(currentStep),
    formData,
    errors,

    // Computed
    isFirstStep,
    isLastStep,
    currentStepData,
    canProceed,
    progress,

    // Methods
    nextStep,
    previousStep,
    goToStep,
    validateCurrentStep,
    validateAllSteps,
    resetForm,
    setFieldValue,
    setFieldError,
    clearFieldError,
  }
}

// Helper function to create step indicators styling
export function useStepIndicator(currentStep: number, stepNumber: number) {
  return computed(() => ({
    'bg-blue-600 text-white': currentStep >= stepNumber,
    'bg-gray-200 text-gray-500': currentStep < stepNumber,
    'border-blue-600': currentStep >= stepNumber,
    'border-gray-200': currentStep < stepNumber,
  }))
}
