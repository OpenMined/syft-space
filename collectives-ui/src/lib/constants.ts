/**
 * Application constants
 */

// Form steps for create endpoint pages
export const CREATE_ENDPOINT_STEPS = {
  BASIC_INFO: 1,
  DATA_SOURCE: 2,
  OUTPUT: 3,
  POLICIES: 4,
  REVIEW: 5,
} as const

export const CREATE_MODEL_ENDPOINT_STEPS = {
  BASIC_INFO: 1,
  MODEL: 2,
  POLICIES: 3,
  REVIEW: 4,
} as const

// Status options
export const STATUS_OPTIONS = {
  RUNNING: 'running',
  STOPPED: 'stopped',
  PUBLISHED: 'published',
  DRAFT: 'draft',
} as const

// Model types
export const MODEL_TYPES = {
  VLLM: 'vllm',
  OLLAMA: 'ollama',
  HUGGINGFACE: 'huggingface',
} as const

// Data source types
export const DATA_SOURCE_TYPES = {
  WEAVIATE: 'weaviate',
  QDRANT: 'qdrant',
  FILESYSTEM: 'filesystem',
  CHROMA: 'chroma',
} as const

// Error types
export const ERROR_TYPES = {
  VALIDATION: 'validation',
  NETWORK: 'network',
  SERVER: 'server',
  UNKNOWN: 'unknown',
} as const

// Common validation rules
export const VALIDATION_RULES = {
  REQUIRED: 'This field is required',
  MIN_LENGTH: (min: number) => `Must be at least ${min} characters`,
  MAX_LENGTH: (max: number) => `Must be no more than ${max} characters`,
  INVALID_FORMAT: 'Invalid format',
} as const

// HTTP Status codes
export const HTTP_STATUS = {
  CLIENT_ERROR_START: 400,
  SERVER_ERROR_START: 500,
  UNPROCESSABLE_ENTITY: 422,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  INTERNAL_SERVER_ERROR: 500,
} as const

// Time calculations
export const TIME_CONSTANTS = {
  MINUTE_IN_MS: 60 * 1000,
  HOUR_IN_MS: 60 * 60 * 1000,
  DAY_IN_MS: 24 * 60 * 60 * 1000,
} as const

// Form and UI Constants
export const UI_CONSTANTS = {
  // Form validation
  FORM_VALIDATION_LIMITS: {
    NAME_MIN_LENGTH: 2,
    NAME_MAX_LENGTH: 100,
    DESCRIPTION_MIN_LENGTH: 10,
    DESCRIPTION_MAX_LENGTH: 1000,
  },

  // Animation timing
  ANIMATION_DURATIONS: {
    FAST: 200,
    NORMAL: 300,
    SLOW: 500,
  },

  // Component dimensions
  DIALOG_DEFAULT_HEIGHT: 400,

  // Delays and timeouts
  DEFAULT_SEARCH_DEBOUNCE_MS: 300,
  API_SIMULATION_DELAY: 1000,
  DEFAULT_RETRY_DELAY: 1000,
  TOOLTIP_NO_DELAY: 0,
  DEFAULT_MANUAL_APPROVAL_TIMEOUT: '24',
  ERROR_AUTO_CLEAR_DELAY: 5000,
} as const

// Application limits
export const APP_LIMITS = {
  MAX_ERROR_HISTORY_SIZE: 10,
  TOTAL_ENDPOINT_CREATION_STEPS: 5,
  TOTAL_MODEL_ENDPOINT_CREATION_STEPS: 4,
  PERCENTAGE_MULTIPLIER: 100,
} as const

// File size constants
export const FILE_SIZE_CONSTANTS = {
  KB: 1024,
  MB: 1024 * 1024,
  GB: 1024 * 1024 * 1024,
} as const

// Type utilities
export type ValueOf<T> = T[keyof T]
export type TimestampField = Date
export type OptionalTimestampField = Date | undefined
