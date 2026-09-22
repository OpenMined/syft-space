<template>
  <div class="space-y-6">
    <section v-for="group in groups" :key="group.code" class="space-y-3">
      <div>
        <h3 class="text-sm font-medium text-foreground">{{ group.words.label }}</h3>
        <p v-if="group.words.help" class="text-xs text-muted-foreground mt-0.5 max-w-2xl">
          {{ group.words.help }}
        </p>
      </div>

      <div class="space-y-4 pl-1">
        <div v-for="field in group.fields" :key="field.name" class="space-y-1.5">
          <div class="flex items-baseline justify-between gap-3">
            <Label :for="field.name" class="text-sm text-foreground">
              {{ wordsFor(field.name).label }}
            </Label>
            <button
              v-if="isSet(field.name)"
              type="button"
              class="text-[11px] text-muted-foreground hover:text-foreground underline underline-offset-2"
              @click="clear(field.name)"
            >
              {{ inheritLabel }}
            </button>
            <span v-else class="text-[11px] text-muted-foreground">
              {{ inheritedText(field) }}
            </span>
          </div>

          <!-- A list too long to inline, named by the benchmark rather than
               shipped with the field. First, because a catalogue field may be
               of any type and what matters is where its values live. -->
          <ModelPicker
            v-if="field.catalog === 'models'"
            :model-value="modelPickerValue(field.name)"
            :multiple="field.type === 'array'"
            :connection-id="connectionId"
            :placeholder="placeholder(field)"
            @update:model-value="(v) => write(field.name, v)"
          />

          <!-- A list of choices: each value is on or off, and none of them
               being on is itself a decision the benchmark honours. -->
          <div
            v-else-if="field.type === 'array' && field.choices"
            class="flex flex-wrap gap-x-4 gap-y-2 pt-0.5"
          >
            <label
              v-for="choice in field.choices"
              :key="String(choice)"
              class="flex items-center gap-2 text-xs text-foreground cursor-pointer"
            >
              <Checkbox
                :model-value="listHas(field, choice)"
                @update:model-value="(on) => toggle(field, choice, on === true)"
              />
              {{ choice }}
            </label>
          </div>

          <!-- A free list: temperatures, spaCy models. Typed as text because
               the set of valid values is nobody's to enumerate — a list that
               is enumerable arrives with `choices`, and one that is long but
               known arrives with `catalog`. -->
          <Input
            v-else-if="field.type === 'array'"
            :id="field.name"
            :model-value="listText(field.name)"
            :placeholder="placeholder(field)"
            class="h-9"
            @update:model-value="(v: string | number) => setList(field, String(v))"
          />

          <!-- One choice out of a known set. -->
          <Select
            v-else-if="field.choices"
            :model-value="(value(field.name) as string) ?? INHERIT"
            @update:model-value="(v: unknown) => setChoice(field.name, v)"
          >
            <SelectTrigger class="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="INHERIT">{{ inheritedText(field) }}</SelectItem>
              <SelectItem
                v-for="choice in field.choices"
                :key="String(choice)"
                :value="String(choice)"
              >
                {{ choice }}
              </SelectItem>
            </SelectContent>
          </Select>

          <!-- Three states, not two. "Unset" is not "off": it means the
               benchmark's own answer, and a two-state switch would silently
               turn inheritance into a decision. -->
          <Select
            v-else-if="field.type === 'boolean'"
            :model-value="boolText(field.name)"
            @update:model-value="(v: unknown) => setBool(field.name, v)"
          >
            <SelectTrigger class="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="INHERIT">{{ inheritedText(field) }}</SelectItem>
              <SelectItem value="true">Yes</SelectItem>
              <SelectItem value="false">No</SelectItem>
            </SelectContent>
          </Select>

          <Input
            v-else-if="field.type === 'integer' || field.type === 'number'"
            :id="field.name"
            type="number"
            :min="field.minimum"
            :max="field.maximum"
            :step="field.type === 'integer' ? 1 : 'any'"
            :model-value="(value(field.name) as number | undefined) ?? ''"
            :placeholder="placeholder(field)"
            class="h-9"
            @update:model-value="(v: string | number) => setNumber(field, v)"
          />

          <Input
            v-else
            :id="field.name"
            :model-value="(value(field.name) as string | undefined) ?? ''"
            :placeholder="placeholder(field)"
            class="h-9"
            @update:model-value="(v: string | number) => setText(field.name, String(v))"
          />

          <p v-if="wordsFor(field.name).help" class="text-xs text-muted-foreground max-w-2xl">
            {{ wordsFor(field.name).help }}
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * A settings layer, drawn from the benchmark's own description of its fields.
 *
 * Nothing here knows what a benchmark setting means. The benchmark sends names,
 * types, ranges and choices; `labels.ts` supplies the words; this draws the
 * controls. A benchmark that grows a setting gets a form for it the same day,
 * without a migration or a release on this side.
 *
 * The one idea the form does carry is **inheritance**. Every field has three
 * states, not two: set here, or taken from the layer above. An empty box is
 * not a zero and must never be sent as one — so unset fields are simply absent
 * from the document, and what they would turn into is shown beside them.
 */
import { computed } from 'vue'

import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { BenchmarkField, BenchmarkLayer } from '@/api/types'
import { groupWords, wordsFor } from './labels'

const INHERIT = '__inherit__'

const props = withDefaults(
  defineProps<{
    fields: BenchmarkField[]
    modelValue: BenchmarkLayer
    /** What an unset field turns into: the layer above, then the installation. */
    inherited?: BenchmarkLayer
    inheritLabel?: string
    /**
     * Whose catalogue a field with `catalog` draws from. Optional: not every
     * layer has such a field, and a form for a benchmark that is gone must
     * still open — without it the picker takes a typed name.
     */
    connectionId?: string
  }>(),
  { inherited: () => ({}), inheritLabel: 'Clear', connectionId: '' },
)

const emit = defineEmits<{ 'update:modelValue': [BenchmarkLayer] }>()

const groups = computed(() => {
  const order: string[] = []
  const buckets = new Map<string, BenchmarkField[]>()
  for (const field of props.fields) {
    if (!buckets.has(field.group)) {
      buckets.set(field.group, [])
      order.push(field.group)
    }
    buckets.get(field.group)!.push(field)
  }
  return order.map((code) => ({
    code,
    words: groupWords(code),
    fields: buckets.get(code)!,
  }))
})

function value(name: string): unknown {
  return props.modelValue[name]
}

/** `value()`, typed for ModelPicker's v-model — a catalog field is a string or a list of them. */
function modelPickerValue(name: string): string | string[] | undefined {
  return value(name) as string | string[] | undefined
}

function isSet(name: string): boolean {
  return Object.prototype.hasOwnProperty.call(props.modelValue, name)
}

function write(name: string, next: unknown): void {
  const out = { ...props.modelValue }
  if (next === undefined) {
    delete out[name]
  } else {
    out[name] = next
  }
  emit('update:modelValue', out)
}

function clear(name: string): void {
  write(name, undefined)
}

/** What this field falls back to, in words. */
function inheritedText(field: BenchmarkField): string {
  const fallback = props.inherited[field.name]
  if (fallback === undefined || fallback === null) return 'Default'
  if (Array.isArray(fallback)) {
    return fallback.length ? `Default: ${fallback.join(', ')}` : 'Default: none'
  }
  if (typeof fallback === 'boolean') return `Default: ${fallback ? 'yes' : 'no'}`
  return `Default: ${fallback}`
}

function placeholder(field: BenchmarkField): string {
  const fallback = props.inherited[field.name]
  if (fallback === undefined || fallback === null) return ''
  return Array.isArray(fallback) ? fallback.join(', ') : String(fallback)
}

// --- lists ------------------------------------------------------------------

function currentList(field: BenchmarkField): unknown[] {
  const own = props.modelValue[field.name]
  if (Array.isArray(own)) return own
  const fallback = props.inherited[field.name]
  return Array.isArray(fallback) ? fallback : []
}

function listHas(field: BenchmarkField, choice: string | number): boolean {
  return currentList(field).some((item) => String(item) === String(choice))
}

function toggle(field: BenchmarkField, choice: string | number, on: boolean): void {
  const base = currentList(field).map(String)
  const next = on
    ? [...new Set([...base, String(choice)])]
    : base.filter((item) => item !== String(choice))
  // Order follows the benchmark's own, not the order of clicking: arms and
  // checks are declared in the order they run, and a form should not reshuffle
  // what the service will do.
  const ordered = (field.choices ?? []).map(String).filter((c) => next.includes(c))
  write(field.name, ordered.length ? ordered : next)
}

function listText(name: string): string {
  const own = props.modelValue[name]
  return Array.isArray(own) ? own.join(', ') : ''
}

/**
 * One entry of a free list, as the owner pasted it.
 *
 * A list of model names travels between a config file, documentation and this
 * box, and on the way it keeps the punctuation of wherever it came from:
 * `"a/b", "c/d"` out of JSON, `["a/b", "c/d"]` out of an array. Split on the
 * comma alone, the quotes stay inside the name — and a quoted name is refused
 * by the provider on every single call, after the whole run has been paid for.
 *
 * Only the wrappers at the ends go. What is left inside is left alone: a value
 * that still looks wrong is the benchmark's to refuse, with the reason, rather
 * than this form's to guess at.
 */
function unwrap(part: string): string {
  return part.replace(/^[\s"'`[\]{}]+/, '').replace(/[\s"'`[\]{}]+$/, '')
}

function setList(field: BenchmarkField, text: string): void {
  const parts = text.split(',').map(unwrap).filter(Boolean)
  if (!text.trim()) {
    // An empty box means "not set here", not "an empty list". Clearing a list
    // deliberately is done with the Clear control, which says what it does.
    write(field.name, undefined)
    return
  }
  write(
    field.name,
    field.item_type === 'number' || field.item_type === 'integer'
      ? parts.map(Number).filter((n) => !Number.isNaN(n))
      : parts,
  )
}

// --- scalars ----------------------------------------------------------------

function setChoice(name: string, next: unknown): void {
  write(name, next === INHERIT || next === undefined ? undefined : next)
}

function boolText(name: string): string {
  const own = props.modelValue[name]
  if (typeof own !== 'boolean') return INHERIT
  return own ? 'true' : 'false'
}

function setBool(name: string, next: unknown): void {
  write(name, next === INHERIT || next === undefined ? undefined : next === 'true')
}

function setNumber(field: BenchmarkField, raw: string | number): void {
  const text = String(raw).trim()
  if (!text) {
    write(field.name, undefined)
    return
  }
  const parsed = Number(text)
  write(field.name, Number.isNaN(parsed) ? undefined : parsed)
}

function setText(name: string, raw: string): void {
  write(name, raw.trim() ? raw : undefined)
}
</script>
