/**
 * Composable for form validation
 * Provides validation rules and helpers
 */

import { reactive, computed } from 'vue'
import { VALIDATION_RULES, UI_CONSTANTS } from '@/lib/constants'

type ValidationResult = string | null

export interface ValidationRule<T = unknown> {
  required?: boolean
  minLength?: number
  maxLength?: number
  pattern?: RegExp
  custom?: (value: T) => ValidationResult
}

export interface FieldValidation<T = unknown> {
  rules: ValidationRule<T>
  touched: boolean
  error: ValidationResult
}

export function useFormValidation<TFormData extends Record<string, unknown> = Record<string, unknown>>() {
  const fields = reactive<Record<keyof TFormData, FieldValidation>>({})

  // Register a field for validation
  const registerField = <K extends keyof TFormData>(name: K, rules: ValidationRule<TFormData[K]>) => {
    fields[name] = {
      rules,
      touched: false,
      error: null
    }
  }

  // Validate a single field
  const validateField = <K extends keyof TFormData>(name: K, value: TFormData[K]): ValidationResult => {
    const field = fields[name]
    if (!field) return null

    const { rules } = field

    // Required validation
    if (rules.required && (!value || (typeof value === 'string' && value.trim() === ''))) {
      return VALIDATION_RULES.REQUIRED
    }

    // Skip other validations if field is empty and not required
    if (!value || (typeof value === 'string' && value.trim() === '')) {
      return null
    }

    // Min length validation
    if (rules.minLength && typeof value === 'string' && value.length < rules.minLength) {
      return VALIDATION_RULES.MIN_LENGTH(rules.minLength)
    }

    // Max length validation
    if (rules.maxLength && typeof value === 'string' && value.length > rules.maxLength) {
      return VALIDATION_RULES.MAX_LENGTH(rules.maxLength)
    }

    // Pattern validation
    if (rules.pattern && typeof value === 'string' && !rules.pattern.test(value)) {
      return VALIDATION_RULES.INVALID_FORMAT
    }

    // Custom validation
    if (rules.custom) {
      const customError = rules.custom(value)
      if (customError) return customError
    }

    return null
  }

  // Set field as touched and validate
  const touchField = (name: string, value: any) => {
    const field = fields[name]
    if (field) {
      field.touched = true
      field.error = validateField(name, value)
    }
  }

  // Validate all fields
  const validateAll = (formData: Record<string, any>): boolean => {
    let isValid = true
    
    Object.keys(fields).forEach(name => {
      const field = fields[name]
      field.touched = true
      field.error = validateField(name, formData[name])
      if (field.error) {
        isValid = false
      }
    })

    return isValid
  }

  // Get field error
  const getFieldError = (name: string): string | null => {
    const field = fields[name]
    return field?.touched ? field.error : null
  }

  // Check if field has error
  const hasFieldError = (name: string): boolean => {
    return !!getFieldError(name)
  }

  // Get all errors
  const errors = computed(() => {
    const errorObj: Record<string, string> = {}
    Object.keys(fields).forEach(name => {
      const error = getFieldError(name)
      if (error) {
        errorObj[name] = error
      }
    })
    return errorObj
  })

  // Check if form is valid
  const isValid = computed(() => {
    return Object.keys(fields).every(name => !hasFieldError(name))
  })

  // Reset validation state
  const reset = () => {
    Object.keys(fields).forEach(name => {
      const field = fields[name]
      field.touched = false
      field.error = null
    })
  }

  return {
    fields,
    registerField,
    validateField,
    touchField,
    validateAll,
    getFieldError,
    hasFieldError,
    errors,
    isValid,
    reset
  }
}

// Common validation rules
export const commonRules = {
  required: { required: true },
  requiredString: { required: true, minLength: 1 },
  name: { required: true, minLength: UI_CONSTANTS.FORM_VALIDATION_LIMITS.NAME_MIN_LENGTH, maxLength: UI_CONSTANTS.FORM_VALIDATION_LIMITS.NAME_MAX_LENGTH },
  description: { required: true, minLength: UI_CONSTANTS.FORM_VALIDATION_LIMITS.DESCRIPTION_MIN_LENGTH, maxLength: UI_CONSTANTS.FORM_VALIDATION_LIMITS.DESCRIPTION_MAX_LENGTH },
  url: { 
    pattern: /^https?:\/\/[^\s/$.?#].[^\s]*$/i 
  },
  email: { 
    pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/ 
  }
}