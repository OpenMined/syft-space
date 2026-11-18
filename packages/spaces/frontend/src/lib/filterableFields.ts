import type { FilterSchema, FilterFieldSpec } from '@/api/types'

// One row of the filterable-fields picker: a field the store can filter on,
// or a saved name the schema no longer declares (`spec` null).
export interface FilterFieldRow {
  name: string
  spec: FilterFieldSpec | null
  checked: boolean
}

// `null` = every declared field, `[]` = filtering off, a list = those fields.
export type Allowlist = string[] | null

export const filteringDisabled = (allowlist: Allowlist): boolean =>
  allowlist !== null && allowlist.length === 0

// Schema fields in declaration order, then saved names the schema lost.
export function filterRows(schema: FilterSchema, allowlist: Allowlist): FilterFieldRow[] {
  const names = Object.keys(schema.fields)
  const rows: FilterFieldRow[] = names.map((name) => ({
    name,
    spec: schema.fields[name] ?? null,
    checked: allowlist === null || allowlist.includes(name),
  }))
  for (const name of allowlist ?? []) {
    if (!names.includes(name)) rows.push({ name, spec: null, checked: false })
  }
  return rows
}

// What to store for a set of ticked names: `null` once every declared field
// is ticked (so fields declared later are included too), else the list.
export function allowlistFor(schema: FilterSchema, checked: string[]): Allowlist {
  const names = Object.keys(schema.fields)
  const kept = names.filter((name) => checked.includes(name))
  return kept.length === names.length ? null : kept
}

export const allowlistChanged = (a: Allowlist, b: Allowlist): boolean =>
  JSON.stringify(a) !== JSON.stringify(b)

export function describeAllowlist(allowlist: Allowlist): string {
  if (allowlist === null) return 'All declared fields'
  if (allowlist.length === 0) return 'Filtering disabled'
  return `${allowlist.length} ${allowlist.length === 1 ? 'field' : 'fields'}`
}

// Beside the picker's heading: "All 5 fields", "2 of 5 fields", "Off".
export function summarizeAllowlist(schema: FilterSchema, allowlist: Allowlist): string {
  const total = Object.keys(schema.fields).length
  const fields = (n: number) => `${n} ${n === 1 ? 'field' : 'fields'}`
  if (filteringDisabled(allowlist)) return 'Off'
  if (allowlist === null) return `All ${fields(total)}`
  const kept = allowlist.filter((name) => name in schema.fields).length
  return `${kept} of ${fields(total)}`
}
