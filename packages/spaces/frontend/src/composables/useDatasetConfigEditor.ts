import { computed, ref } from 'vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { ConfigSchema, ConnectionHealth } from '@/api/types'
import { sourcePresentation } from '@/config/sources'
import { apiErrorMessage } from '@/lib/apiError'
import {
  configurationPatch,
  draftErrors,
  draftFromStored,
  editableFields,
  fieldsByAxis,
  type ConfigField,
  type FieldDraft,
} from '@/lib/datasetConfig'

/**
 * Holds the editable half of a dataset's configuration while an owner edits
 * it: the type's schema, one draft per editable field, and what those drafts
 * mean as a PATCH. The backend remains the judge: its 400/422 reply is
 * surfaced as `serverError`.
 */
export function useDatasetConfigEditor() {
  const schema = ref<ConfigSchema | null>(null)
  const fields = ref<ConfigField[]>([])
  const stored = ref<Record<string, unknown>>({})
  const drafts = ref<Record<string, FieldDraft>>({})
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const serverError = ref<string | null>(null)
  const health = ref<ConnectionHealth | null>(null)
  const testing = ref(false)

  const groups = computed(() => fieldsByAxis(fields.value))
  const errors = computed(() => draftErrors(fields.value, drafts.value))
  const patch = computed(() => configurationPatch(fields.value, stored.value, drafts.value))
  const hasChanges = computed(() => Object.keys(patch.value).length > 0)
  const isValid = computed(() => Object.keys(errors.value).length === 0)

  const load = async (dtype: string, configuration: Record<string, unknown>) => {
    loading.value = true
    loadError.value = null
    serverError.value = null
    health.value = null
    stored.value = { ...configuration }
    try {
      const type = await datasetsApi.getType(dtype)
      schema.value = type.config_schema
      fields.value = editableFields(type.config_schema, sourcePresentation(dtype).fields)
      drafts.value = Object.fromEntries(
        fields.value.map((f) => [f.name, draftFromStored(f, configuration[f.name])]),
      )
    } catch (err) {
      schema.value = null
      fields.value = []
      drafts.value = {}
      loadError.value = apiErrorMessage(err, 'Could not load the configuration schema')
    } finally {
      loading.value = false
    }
  }

  const setDraft = (name: string, draft: FieldDraft) => {
    drafts.value = { ...drafts.value, [name]: draft }
    serverError.value = null
    health.value = null
  }

  /** Dry-run the drafted configuration against the live service; nothing is saved. */
  const testConnection = async (datasetName: string) => {
    testing.value = true
    serverError.value = null
    try {
      health.value = await datasetsApi.healthcheckWith(datasetName, patch.value)
    } catch (err) {
      health.value = null
      serverError.value = apiErrorMessage(err, 'Connection test failed')
    } finally {
      testing.value = false
    }
  }

  const reset = () => {
    schema.value = null
    fields.value = []
    stored.value = {}
    drafts.value = {}
    loadError.value = null
    serverError.value = null
    health.value = null
  }

  return {
    schema,
    fields,
    groups,
    drafts,
    errors,
    patch,
    hasChanges,
    isValid,
    loading,
    loadError,
    serverError,
    health,
    testing,
    load,
    setDraft,
    testConnection,
    reset,
  }
}
