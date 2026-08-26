<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[520px] max-h-[85vh] flex flex-col">
      <DialogHeader>
        <DialogTitle class="heading-3">Choose data source</DialogTitle>
        <DialogDescription>
          Pick where this dataset's content comes from. Credentials are kept in the browser until
          you create the dataset.
        </DialogDescription>
      </DialogHeader>

      <!-- Only the body scrolls, so a long field can never push Continue out
           of reach. Scrolling one axis clips the other, which would shear off
           an input's 3px focus ring — the padding gives the ring room and the
           matching negative margin keeps fields aligned with the header. -->
      <div class="space-y-6 mt-4 flex-1 overflow-y-auto min-h-0 -mx-1 px-1">
        <div class="space-y-2">
          <Label for="source-type" class="text-sm font-medium">
            Source type <span class="text-red-500">*</span>
          </Label>
          <Select v-model="selectedSourceId">
            <SelectTrigger id="source-type" class="w-full">
              <SelectValue
                :placeholder="loadError ? 'Failed to load sources' : 'Select a source type'"
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="source in browsableTypes" :key="source.name" :value="source.name">
                <span class="mr-2">{{ presentation(source.name).icon }}</span>
                {{ presentation(source.name).label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p v-if="loadError" class="text-xs text-destructive">{{ loadError }}</p>
          <p v-else-if="selectedType" class="text-xs text-muted-foreground">
            {{ selectedDescription }}
          </p>
        </div>

        <div v-if="requiredFields.length > 0" class="space-y-4">
          <div v-for="field in requiredFields" :key="field.name" class="space-y-2">
            <Label :for="`cred-${field.name}`" class="text-sm font-medium">
              {{ field.label }} <span class="text-red-500">*</span>
              <span
                v-if="field.isList && listCount(field.name) > 0"
                class="text-muted-foreground ml-1 font-normal"
              >
                ({{ listCount(field.name) }})
              </span>
            </Label>

            <!-- List field: a fixed-height editable list with a +/- toolbar.
                 Bounded height is what keeps a long list from growing the
                 dialog; rows stay editable so a typo in a long URL can be
                 fixed in place. -->
            <template v-if="field.isList">
              <div class="border-input rounded-md border">
                <div class="max-h-[158px] min-h-[112px] overflow-y-auto">
                  <input
                    v-for="(row, index) in listRows[field.name] ?? []"
                    :key="index"
                    :ref="(el) => setRowRef(field.name, index, el)"
                    :value="row"
                    :placeholder="field.placeholder"
                    class="w-full bg-transparent px-3 py-1.5 text-sm outline-none focus:bg-accent"
                    :class="{ 'bg-accent/50': listSelected[field.name] === index }"
                    @input="onRowInput(field.name, index, $event)"
                    @focus="listSelected[field.name] = index"
                    @blur="onRowBlur(field.name, index)"
                    @paste="onRowPaste(field.name, index, $event)"
                  />
                  <p
                    v-if="(listRows[field.name]?.length ?? 0) === 0"
                    class="text-muted-foreground px-3 py-1.5 text-sm"
                  >
                    {{ field.placeholder }}
                  </p>
                </div>
                <div class="border-input flex items-center gap-1 border-t px-1 py-0.5">
                  <button
                    type="button"
                    class="text-muted-foreground hover:text-foreground hover:bg-accent rounded px-2 py-0.5 text-base leading-none"
                    :aria-label="`Add ${field.label}`"
                    @click="addRow(field.name)"
                  >
                    +
                  </button>
                  <span class="bg-border h-4 w-px" />
                  <button
                    type="button"
                    class="text-muted-foreground hover:text-foreground hover:bg-accent rounded px-2 py-0.5 text-base leading-none disabled:opacity-40 disabled:hover:bg-transparent"
                    :disabled="(listRows[field.name]?.length ?? 0) === 0"
                    :aria-label="`Remove ${field.label}`"
                    @click="removeRow(field.name)"
                  >
                    −
                  </button>
                </div>
              </div>
              <p v-if="listHint[field.name]" class="text-muted-foreground text-xs">
                {{ listHint[field.name] }}
              </p>
            </template>

            <Input
              v-else
              :id="`cred-${field.name}`"
              v-model="credentials[field.name]"
              :type="field.type"
              :placeholder="field.placeholder"
              class="w-full"
            />
          </div>
        </div>
      </div>

      <DialogFooter class="mt-6 flex-shrink-0">
        <Button variant="outline" @click="handleCancel">Cancel</Button>
        <Button @click="handleContinue" :disabled="!canContinue">Continue</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { datasetsApi } from '@/api/endpoints/datasets'
import type { DatasetTypeInfoResponse } from '@/api/types'

interface FieldCopy {
  label?: string
  placeholder?: string
  // Render as a chip list. Values are joined with `separator` into the
  // single string the backend config field expects.
  list?: { separator: string }
}

interface SourceCopy {
  label: string
  icon: string
  description?: string
  fields?: Record<string, FieldCopy>
}

// Presentation layer: all user-facing copy lives here, keyed by source type.
// The backend schema supplies structure (which fields, required, type/format)
// and is the fallback for labels/description when an entry is missing here.
const PRESENTATION: Record<string, SourceCopy> = {
  local_file: {
    label: 'Local files',
    icon: '📁',
    description: 'Files and folders from this machine.',
  },
  wordpress: {
    label: 'WordPress',
    icon: '📰',
    description: 'Posts and pages from a self-hosted WordPress site.',
    fields: {
      siteUrl: { label: 'Site URL', placeholder: 'https://example.com' },
      username: { label: 'Username', placeholder: 'wp-admin user_login' },
      applicationPassword: {
        label: 'Application password',
        placeholder: 'Generate under Users → Profile → Application Passwords',
      },
    },
  },
  blogspot: {
    label: 'Blogspot',
    icon: '✍️',
    description: 'Posts from public Blogger blogs. One API key covers any number of blogs.',
    fields: {
      blogUrls: {
        label: 'Blog URLs',
        placeholder: 'https://example.blogspot.com',
        list: { separator: ',' },
      },
      apiKey: {
        label: 'API key',
        placeholder: 'Google API key with the Blogger API enabled',
      },
    },
  },
}

const presentation = (name: string): SourceCopy => PRESENTATION[name] ?? { label: name, icon: '🗂️' }

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  continue: [payload: { sourceType: string; credentials: Record<string, string> }]
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const types = ref<DatasetTypeInfoResponse[]>([])
const loadError = ref<string | null>(null)
const selectedSourceId = ref<string>('')
const credentials = ref<Record<string, string>>({})

const loadTypes = async () => {
  try {
    loadError.value = null
    types.value = await datasetsApi.listTypes()
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Failed to load source types'
  }
}

onMounted(loadTypes)

const browsableTypes = computed(() => types.value.filter((t) => t.browsable))

const selectedType = computed(
  () => browsableTypes.value.find((t) => t.name === selectedSourceId.value) ?? null,
)

const selectedDescription = computed(() => {
  const type = selectedType.value
  if (!type) return ''
  return presentation(type.name).description ?? type.description
})

const requiredFields = computed(() => {
  const type = selectedType.value
  const schema = type?.browse_schema
  if (!type || !schema?.properties) return []
  const fieldCopy = presentation(type.name).fields ?? {}
  return (schema.required ?? []).map((name) => {
    const prop = schema.properties?.[name]
    const copy = fieldCopy[name]
    return {
      name,
      label: copy?.label ?? prop?.title ?? name,
      placeholder: copy?.placeholder ?? '',
      type: prop?.format === 'password' ? 'password' : 'text',
      isList: Boolean(copy?.list),
      separator: copy?.list?.separator ?? ',',
    }
  })
})

// ── List fields ────────────────────────────────────────────────────────
// The backend takes one separated string per field, so the rows live here
// and are joined into `credentials` on every edit. Everything downstream —
// validation, canContinue, the emitted payload — still sees a plain string.
//
// Rows are kept exactly as typed and only normalized on blur: rewriting the
// text mid-keystroke (stripping the trailing slash the user is still typing)
// fights the person at the keyboard.

const listRows = ref<Record<string, string[]>>({})
const listSelected = ref<Record<string, number>>({})
const listHint = ref<Record<string, string>>({})
const rowRefs = new Map<string, HTMLInputElement>()

const setRowRef = (name: string, index: number, el: unknown) => {
  const key = `${name}:${index}`
  if (el instanceof HTMLInputElement) rowRefs.set(key, el)
  else rowRefs.delete(key)
}

/** Trailing slashes are insignificant to Blogger, so `foo.com/` == `foo.com`. */
const normalizeListValue = (value: string) => value.trim().replace(/\/+$/, '')

/** How many rows will actually be stored — blanks and duplicates excluded. */
const listCount = (name: string) => {
  const seen = new Set<string>()
  for (const row of listRows.value[name] ?? []) {
    const normalized = normalizeListValue(row)
    if (normalized) seen.add(normalized)
  }
  return seen.size
}

/** Join the rows into the single separated string the config field stores. */
const syncRows = (name: string) => {
  const field = requiredFields.value.find((f) => f.name === name)
  const seen = new Set<string>()
  const kept: string[] = []
  for (const row of listRows.value[name] ?? []) {
    const normalized = normalizeListValue(row)
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    kept.push(normalized)
  }
  credentials.value[name] = kept.join(field?.separator ?? ',')
}

const onRowInput = (name: string, index: number, event: Event) => {
  const rows = [...(listRows.value[name] ?? [])]
  rows[index] = (event.target as HTMLInputElement).value
  listRows.value[name] = rows
  syncRows(name)
}

const onRowBlur = (name: string, index: number) => {
  const rows = [...(listRows.value[name] ?? [])]
  const normalized = normalizeListValue(rows[index] ?? '')
  const isDuplicate =
    normalized !== '' && rows.some((r, i) => i !== index && normalizeListValue(r) === normalized)

  if (isDuplicate) {
    rows.splice(index, 1)
    listHint.value[name] = 'Already added — that duplicate was removed.'
  } else {
    rows[index] = normalized
    listHint.value[name] = ''
  }
  listRows.value[name] = rows
  syncRows(name)
}

/** Pasting a separated list fills one row per value instead of one long row. */
const onRowPaste = (name: string, index: number, event: ClipboardEvent) => {
  const field = requiredFields.value.find((f) => f.name === name)
  const separator = field?.separator ?? ','
  const text = event.clipboardData?.getData('text') ?? ''
  if (!text.includes(separator) && !text.includes('\n')) return

  event.preventDefault()
  const pasted = text
    .split(new RegExp(`[${separator}\n]`))
    .map(normalizeListValue)
    .filter(Boolean)
  const rows = [...(listRows.value[name] ?? [])]
  rows.splice(index, 1, ...pasted)
  listRows.value[name] = rows
  listSelected.value[name] = Math.min(index + pasted.length - 1, rows.length - 1)
  syncRows(name)
}

const addRow = async (name: string) => {
  const rows = [...(listRows.value[name] ?? []), '']
  listRows.value[name] = rows
  listSelected.value[name] = rows.length - 1
  await nextTick()
  rowRefs.get(`${name}:${rows.length - 1}`)?.focus()
}

/** Remove the selected row, falling back to the last one. */
const removeRow = async (name: string) => {
  const rows = [...(listRows.value[name] ?? [])]
  if (rows.length === 0) return
  const index = Math.min(listSelected.value[name] ?? rows.length - 1, rows.length - 1)
  rows.splice(index, 1)
  listRows.value[name] = rows
  listSelected.value[name] = Math.min(index, rows.length - 1)
  listHint.value[name] = ''
  syncRows(name)
  await nextTick()
  const next = listSelected.value[name]
  if (next >= 0) rowRefs.get(`${name}:${next}`)?.focus()
}

/** Start list fields with one empty row so the field is usable immediately. */
const seedListRows = () => {
  for (const field of requiredFields.value) {
    if (field.isList && !listRows.value[field.name]) {
      listRows.value[field.name] = ['']
      listSelected.value[field.name] = 0
    }
  }
}

const canContinue = computed(() => {
  if (!selectedType.value) return false
  return requiredFields.value.every((f) => (credentials.value[f.name] ?? '').trim() !== '')
})

const reset = () => {
  selectedSourceId.value = ''
  credentials.value = {}
  listRows.value = {}
  listSelected.value = {}
  listHint.value = {}
  rowRefs.clear()
}

const handleCancel = () => {
  reset()
  isOpen.value = false
}

const handleContinue = () => {
  if (!selectedType.value || !canContinue.value) return
  const trimmed: Record<string, string> = {}
  for (const field of requiredFields.value) {
    trimmed[field.name] = (credentials.value[field.name] ?? '').trim()
  }
  emit('continue', { sourceType: selectedType.value.name, credentials: trimmed })
  reset()
  isOpen.value = false
}

// Clear any entered credentials when switching source type.
watch(selectedSourceId, () => {
  credentials.value = {}
  listRows.value = {}
  listSelected.value = {}
  listHint.value = {}
  rowRefs.clear()
  // Seed after clearing, so the new source's list fields start with one row.
  seedListRows()
})

watch(
  () => props.open,
  (open) => {
    if (!open) reset()
  },
)
</script>
