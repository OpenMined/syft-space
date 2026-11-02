/**
 * Turns a dataset type's composed configuration schema into the fields an
 * owner may edit, and turns what they typed back into the PATCH payload.
 *
 * The backend decides which fields exist, which axis owns them, which are
 * editable and which are secret. Callers pass the human copy for the type
 * (labels, placeholders, list separators); the schema is the fallback.
 * Secret values never reach the client: a stored secret scalar is absent
 * from the dataset's configuration, and a stored secret map keeps its keys
 * with null values. The form therefore edits secrets as "replace or keep".
 */
import type { ConfigSchema, ConfigSchemaProperty } from '@/api/types'
import type { FieldCopy } from '@/config/sources'

export type ConfigAxis = 'source' | 'vector_store'

export const AXIS_LABELS: Record<ConfigAxis, string> = {
  source: 'Source',
  vector_store: 'Vector store',
}

export type ConfigFieldKind = 'text' | 'number' | 'select' | 'list' | 'secret' | 'secretMap'

export interface ConfigField {
  name: string
  axis: ConfigAxis
  label: string
  description: string
  placeholder: string
  required: boolean
  kind: ConfigFieldKind
  // select: the schema's enum, labelled by config/sources.ts when it knows them.
  options: Array<{ value: string; label: string }>
  // list: rows join into one string with `separator`, or stay an array.
  separator?: string
  // secretMap: what one entry is called.
  entryLabel: string
}

/** Draft state of one editable field, as the form holds it. */
export type FieldDraft =
  | { kind: 'value'; value: string }
  | { kind: 'rows'; rows: string[] }
  | { kind: 'secret'; replacement: string }
  | { kind: 'secretMap'; entries: SecretMapEntry[] }

export interface SecretMapEntry {
  key: string
  // null = keep the stored value for this key; a string replaces it.
  value: string | null
  // true when the key existed in the stored map.
  stored: boolean
}

const schemaType = (prop: ConfigSchemaProperty): string | undefined => {
  if (prop.type) return prop.type
  const branch = prop.anyOf?.find((b) => b.type && b.type !== 'null')
  return branch?.type as string | undefined
}

const fieldKind = (prop: ConfigSchemaProperty, hasListCopy: boolean): ConfigFieldKind => {
  const type = schemaType(prop)
  if (prop.visibility === 'secret') return type === 'object' ? 'secretMap' : 'secret'
  if (Array.isArray(prop.enum)) return 'select'
  if (hasListCopy || type === 'array') return 'list'
  if (type === 'integer' || type === 'number') return 'number'
  return 'text'
}

/** The fields an owner may change after creation, in schema order. */
export const editableFields = (
  schema: ConfigSchema,
  copy: Record<string, FieldCopy> = {},
): ConfigField[] => {
  const required = new Set(schema.required ?? [])
  return Object.entries(schema.properties ?? {})
    .filter(([, prop]) => prop.editable === true && prop.visibility !== 'internal')
    .map(([name, prop]) => {
      const fieldCopy = copy[name]
      const kind = fieldKind(prop, Boolean(fieldCopy?.list))
      return {
        name,
        axis: prop.axis ?? 'source',
        label: fieldCopy?.label ?? prop.title ?? name,
        description: prop.description ?? '',
        placeholder: fieldCopy?.placeholder ?? '',
        required: required.has(name),
        kind,
        options: (prop.enum ?? []).map((value) => ({
          value: String(value),
          label: fieldCopy?.choices?.[String(value)] ?? String(value),
        })),
        separator: kind === 'list' ? fieldCopy?.list?.separator : undefined,
        entryLabel: fieldCopy?.entry ?? 'entry',
      }
    })
}

/** Fields grouped by owning axis, axes in a fixed order, empty axes dropped. */
export const fieldsByAxis = (
  fields: ConfigField[],
): Array<{ axis: ConfigAxis; label: string; fields: ConfigField[] }> =>
  (['source', 'vector_store'] as const)
    .map((axis) => ({
      axis,
      label: AXIS_LABELS[axis],
      fields: fields.filter((f) => f.axis === axis),
    }))
    .filter((group) => group.fields.length > 0)

/** Whether the detail page should show a stored value for this key. */
export const isPublicProperty = (schema: ConfigSchema | null, name: string): boolean => {
  const prop = schema?.properties?.[name]
  return prop === undefined || prop.visibility === undefined || prop.visibility === 'public'
}

const listRows = (field: ConfigField, value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String)
  if (typeof value === 'string' && value !== '') return value.split(field.separator ?? ',')
  return []
}

/** The form's starting state for a field, from the stored (redacted) configuration. */
export const draftFromStored = (field: ConfigField, stored: unknown): FieldDraft => {
  switch (field.kind) {
    case 'secret':
      return { kind: 'secret', replacement: '' }
    case 'secretMap':
      return {
        kind: 'secretMap',
        entries: Object.keys(stored && typeof stored === 'object' ? stored : {}).map((key) => ({
          key,
          value: null,
          stored: true,
        })),
      }
    case 'list':
      return { kind: 'rows', rows: listRows(field, stored) }
    default:
      return { kind: 'value', value: stored === undefined || stored === null ? '' : String(stored) }
  }
}

const cleanRows = (rows: string[]): string[] => {
  const seen = new Set<string>()
  const kept: string[] = []
  for (const row of rows) {
    const trimmed = row.trim()
    if (!trimmed || seen.has(trimmed)) continue
    seen.add(trimmed)
    kept.push(trimmed)
  }
  return kept
}

const sameValue = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b)

const capitalize = (word: string): string => word.charAt(0).toUpperCase() + word.slice(1)

/** Validation messages keyed by field name; empty when the drafts can be sent. */
export const draftErrors = (
  fields: ConfigField[],
  drafts: Record<string, FieldDraft>,
): Record<string, string> => {
  const errors: Record<string, string> = {}
  for (const field of fields) {
    const draft = drafts[field.name]
    if (!draft) continue
    if (draft.kind === 'value' && field.required && draft.value.trim() === '') {
      errors[field.name] = `${field.label} is required`
    } else if (draft.kind === 'value' && field.kind === 'number' && draft.value.trim() !== '') {
      if (Number.isNaN(Number(draft.value))) errors[field.name] = `${field.label} must be a number`
    } else if (draft.kind === 'rows' && field.required && cleanRows(draft.rows).length === 0) {
      errors[field.name] = `${field.label} needs at least one entry`
    } else if (draft.kind === 'secretMap') {
      const keys = draft.entries.map((e) => e.key.trim())
      if (keys.some((k) => k === '')) errors[field.name] = `Every ${field.entryLabel} needs a name`
      else if (new Set(keys).size !== keys.length)
        errors[field.name] = `${capitalize(field.entryLabel)} names must be unique`
      else if (draft.entries.some((e) => !e.stored && !e.value))
        errors[field.name] = `New ${field.entryLabel}s need a value`
    }
  }
  return errors
}

/**
 * The `configuration` to PATCH: only the keys whose draft differs from the
 * stored value. Null removes an optional field. For a secret map, every
 * remaining key is sent (null keeps a stored value) so a missing key removes it.
 */
export const configurationPatch = (
  fields: ConfigField[],
  stored: Record<string, unknown>,
  drafts: Record<string, FieldDraft>,
): Record<string, unknown> => {
  const patch: Record<string, unknown> = {}
  for (const field of fields) {
    const draft = drafts[field.name]
    if (!draft) continue
    const storedValue = stored[field.name]
    switch (draft.kind) {
      case 'secret': {
        const replacement = draft.replacement.trim()
        if (replacement !== '') patch[field.name] = replacement
        break
      }
      case 'secretMap': {
        const next: Record<string, string | null> = {}
        for (const entry of draft.entries) next[entry.key.trim()] = entry.value
        const storedKeys = Object.keys(
          storedValue && typeof storedValue === 'object' ? storedValue : {},
        )
        const unchanged =
          storedKeys.length === draft.entries.length &&
          draft.entries.every((e) => e.stored && e.value === null && storedKeys.includes(e.key))
        if (!unchanged) patch[field.name] = Object.keys(next).length === 0 ? null : next
        break
      }
      case 'rows': {
        const rows = cleanRows(draft.rows)
        const next: unknown = field.separator !== undefined ? rows.join(field.separator) : rows
        const empty = rows.length === 0
        if (empty && (storedValue === undefined || storedValue === null)) break
        if (!sameValue(next, storedValue)) patch[field.name] = empty ? null : next
        break
      }
      case 'value': {
        const text = draft.value.trim()
        if (text === '') {
          if (storedValue !== undefined && storedValue !== null && !field.required)
            patch[field.name] = null
          break
        }
        const next: unknown = field.kind === 'number' ? Number(text) : text
        if (!sameValue(next, storedValue)) patch[field.name] = next
        break
      }
    }
  }
  return patch
}
