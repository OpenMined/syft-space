<template>
  <div class="space-y-1.5">
    <Popover v-model:open="open">
      <!-- Anchored to the whole control so the list matches its width. -->
      <PopoverAnchor as-child>
        <div
          class="flex min-h-9 w-full flex-wrap items-center gap-1 rounded-md border bg-transparent px-3 py-1.5 text-sm shadow-xs transition-[color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50"
          :class="warn ? 'border-amber-500' : 'border-input'"
        >
          <!-- One focus stop per chip: its remove button, whose tooltip names the model id. -->
          <template v-if="multiple">
            <Badge v-for="id in selected" :key="id" variant="secondary" class="gap-1 font-normal">
              <Hint :text="id" :focusable="false">
                <span>{{ label(id) }}</span>
              </Hint>
              <Hint :text="`Remove ${id}`" :focusable="false">
                <button
                  type="button"
                  :aria-label="`Remove ${label(id)}`"
                  class="cursor-pointer rounded-xs opacity-60 hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-1"
                  @click="toggle(id)"
                >
                  <X class="size-3" />
                </button>
              </Hint>
            </Badge>
          </template>

          <!-- On the trigger so keyboard focus shows the chosen model's id. -->
          <Hint :text="multiple ? null : selected[0]">
            <PopoverTrigger as-child>
              <button
                :id="triggerId || undefined"
                type="button"
                :aria-describedby="describedBy || undefined"
                class="flex min-w-20 flex-1 cursor-pointer items-center justify-between gap-2 text-left outline-hidden disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span v-if="!selected.length" class="text-muted-foreground">
                  {{ placeholder || 'Choose a model' }}
                </span>
                <span v-else-if="!multiple" class="truncate text-foreground">
                  {{ label(selected[0]!) }}
                </span>
                <span v-else class="text-muted-foreground">{{ addLabel }}</span>

                <ChevronsUpDown class="size-4 shrink-0 opacity-50" />
              </button>
            </PopoverTrigger>
          </Hint>
        </div>
      </PopoverAnchor>

      <PopoverContent class="w-(--reka-popover-trigger-width) p-0" align="start">
        <div class="flex items-center gap-2 border-b border-border/50 px-3">
          <Search class="size-4 shrink-0 opacity-50" />
          <input
            v-model="query"
            :placeholder="'Search ' + catalog.models.length + ' models'"
            class="h-9 w-full bg-transparent text-sm outline-hidden placeholder:text-muted-foreground"
            @keydown.enter.prevent="takeFirst"
          />
        </div>

        <!-- Vendors come from the catalogue. -->
        <div
          v-if="catalog.vendors.length"
          class="flex flex-wrap gap-1 border-b border-border/50 px-2 py-2"
        >
          <button
            type="button"
            class="rounded-md px-1.5 py-0.5 text-[11px] transition-colors"
            :class="pillClass(vendor === '')"
            @click="vendor = ''"
          >
            All
          </button>
          <button
            v-for="name in catalog.vendors"
            :key="name"
            type="button"
            class="rounded-md px-1.5 py-0.5 text-[11px] transition-colors"
            :class="pillClass(vendor === name)"
            @click="vendor = vendor === name ? '' : name"
          >
            {{ name }}
          </button>
        </div>

        <div
          class="flex flex-wrap gap-1 border-b border-border/50 px-2 py-2"
          data-testid="model-filters"
        >
          <Hint v-for="chip in MODEL_FILTERS" :key="chip.value" :text="chip.help">
            <button
              type="button"
              class="rounded-md px-1.5 py-0.5 text-[11px] transition-colors"
              :class="pillClass(filters.includes(chip.value))"
              :aria-pressed="filters.includes(chip.value)"
              @click="filters = toggleFilter(filters, chip.value)"
            >
              {{ chip.label }}
            </button>
          </Hint>
        </div>

        <div class="max-h-72 overflow-y-auto py-1">
          <p v-if="loading" class="px-3 py-6 text-center text-xs text-muted-foreground">
            Loading the catalogue…
          </p>

          <template v-else>
            <!-- Moving names (`~vendor/x-latest`); the pinned model is stored. -->
            <button
              v-for="[name, target] in movingMatches"
              :key="name"
              type="button"
              class="flex w-full items-start justify-between gap-3 px-3 py-1.5 text-left hover:bg-accent/50"
              @click="choose(target)"
            >
              <span class="min-w-0">
                <span class="block truncate text-sm text-foreground">{{ name }}</span>
                <span class="block truncate text-[11px] text-muted-foreground">
                  today this is {{ target }} — that is what will be saved
                </span>
              </span>
              <Badge variant="outline" class="shrink-0 font-normal">moves</Badge>
            </button>

            <button
              v-for="entry in shown"
              :key="entry.id"
              type="button"
              class="flex w-full items-start justify-between gap-3 px-3 py-1.5 text-left hover:bg-accent/50"
              @click="choose(entry.id)"
            >
              <span class="min-w-0">
                <span class="flex items-center gap-1.5">
                  <Check
                    class="size-3.5 shrink-0"
                    :class="selected.includes(entry.id) ? 'opacity-100' : 'opacity-0'"
                  />
                  <span class="truncate text-sm text-foreground">{{
                    modelName(entry.id, entry)
                  }}</span>
                </span>
                <span class="block truncate pl-5 text-[11px] text-muted-foreground">
                  {{ entry.id }}{{ describe(entry) }}
                </span>
              </span>
              <span class="flex shrink-0 items-center gap-1">
                <Hint v-if="webSearchOf(entry) === 'native'" text="Has built-in web search.">
                  <Badge variant="outline" class="font-normal">Web</Badge>
                </Hint>
                <Hint
                  v-else-if="webSearchOf(entry) === 'plugin'"
                  text="Searches through the OpenRouter web plugin."
                >
                  <Badge variant="outline" class="font-normal">Web plugin</Badge>
                </Hint>
                <Hint v-if="!takesTemperature(entry)" text="Takes no temperature setting.">
                  <Badge variant="outline" class="font-normal">No temperature</Badge>
                </Hint>
                <Badge v-if="entry.local" variant="outline" class="font-normal">local</Badge>
                <Badge v-if="entry.retires_on" variant="outline" class="font-normal">
                  retires {{ entry.retires_on }}
                </Badge>
              </span>
            </button>

            <p v-if="hidden > 0" class="px-3 py-1.5 text-[11px] text-muted-foreground">
              and {{ hidden }} more — narrow the search
            </p>

            <!-- A typed name not in the catalogue can still be used. -->
            <button
              v-if="custom"
              type="button"
              class="flex w-full items-start justify-between gap-3 border-t border-border/50 px-3 py-1.5 text-left hover:bg-accent/50"
              @click="choose(custom)"
            >
              <span class="min-w-0">
                <span class="block truncate text-sm text-foreground">Use “{{ custom }}”</span>
                <span class="block truncate text-[11px] text-muted-foreground">
                  not in the catalogue; sent as written
                </span>
              </span>
              <Badge variant="outline" class="shrink-0 font-normal">as typed</Badge>
            </button>

            <p
              v-else-if="!shown.length && !movingMatches.length"
              class="px-3 py-6 text-center text-xs text-muted-foreground"
            >
              Nothing matches.
            </p>
          </template>
        </div>

        <div
          class="flex items-center justify-between gap-2 border-t border-border/50 px-3 py-2 text-[11px] text-muted-foreground"
        >
          <span>{{ age }}</span>
          <button
            type="button"
            class="underline underline-offset-2 hover:text-foreground disabled:no-underline disabled:opacity-60"
            :disabled="refreshing || !connectionId"
            @click="doRefresh"
          >
            {{ refreshing ? 'Refreshing…' : 'Refresh' }}
          </button>
        </div>
      </PopoverContent>
    </Popover>

    <p v-if="error" class="text-xs text-destructive">{{ error }}</p>

    <p v-if="unknown.length" class="text-xs text-muted-foreground">
      Not in the catalogue, sent as written: {{ unknown.join(', ') }}
    </p>
  </div>
</template>

<script setup lang="ts">
/**
 * Model picker over the benchmark's catalogue. A moving name
 * (`~vendor/thing-latest`) is stored as the model it currently points to.
 */
import { computed, ref, watch } from 'vue'
import { Check, ChevronsUpDown, Search, X } from 'lucide-vue-next'

import Hint from '@/components/benchmark/Hint.vue'
import { day, utcStamp } from '@/components/benchmark/report/figures'
import { modelName } from '@/components/benchmark/report/labels'
import { Badge } from '@/components/ui/badge'
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  MODEL_FILTERS,
  matchesFilters,
  takesTemperature,
  toggleFilter,
  webSearchOf,
} from '@/components/benchmark/setup/models'
import type { ModelFilter } from '@/components/benchmark/setup/models'
import { useModelCatalog } from '@/composables/useModelCatalog'
import type { BenchmarkModel } from '@/api/types'

// Rows shown; the rest are counted.
const SHOWN = 80

const props = withDefaults(
  defineProps<{
    modelValue?: string | string[]
    /** Allow several models. */
    multiple?: boolean
    /** Which benchmark's catalogue; without it only typed names work. */
    connectionId?: string
    placeholder?: string
    /** Models not offered, such as the ones other slots already hold. */
    exclude?: string[]
    /** Amber border. */
    warn?: boolean
    /** Id of the control a `<label for>` points at. */
    triggerId?: string
    describedBy?: string
    addLabel?: string
  }>(),
  {
    multiple: false,
    connectionId: '',
    placeholder: '',
    exclude: () => [],
    warn: false,
    triggerId: '',
    describedBy: '',
    addLabel: 'Add another…',
  },
)

const emit = defineEmits<{ 'update:modelValue': [string | string[] | undefined] }>()

const { catalog, loading, refreshing, error, load, refresh } = useModelCatalog()

const open = ref(false)
const query = ref('')
const vendor = ref('')
const filters = ref<ModelFilter[]>([])

// Loaded up front so chosen models show their names; pickers share one cached request.
watch(
  () => props.connectionId,
  (id) => {
    if (id) void load(id)
  },
  { immediate: true },
)

const selected = computed<string[]>(() => {
  const value = props.modelValue
  if (Array.isArray(value)) return value.filter((item): item is string => !!item)
  return typeof value === 'string' && value ? [value] : []
})

const byId = computed(() => new Map(catalog.value.models.map((item) => [item.id, item])))

function label(id: string): string {
  return modelName(id, byId.value.get(id))
}

/** Chosen values not in the catalogue. */
const unknown = computed(() =>
  catalog.value.models.length ? selected.value.filter((id) => !byId.value.has(id)) : [],
)

const needle = computed(() => query.value.trim().toLowerCase())

const matches = computed(() =>
  catalog.value.models.filter((entry) => {
    if (props.exclude.includes(entry.id)) return false
    if (vendor.value && entry.vendor !== vendor.value) return false
    if (!matchesFilters(entry, filters.value)) return false
    if (!needle.value) return true
    return (
      entry.id.toLowerCase().includes(needle.value) ||
      entry.name.toLowerCase().includes(needle.value)
    )
  }),
)

const shown = computed(() => matches.value.slice(0, SHOWN))
const hidden = computed(() => matches.value.length - shown.value.length)

const movingMatches = computed(() => {
  if (vendor.value) return []
  return Object.entries(catalog.value.pins).filter(([name, target]) => {
    if (props.exclude.includes(target)) return false
    if (needle.value && !name.toLowerCase().includes(needle.value)) return false
    if (!filters.value.length) return true
    // Filters apply to the model a moving name points to.
    const entry = byId.value.get(target)
    return !!entry && matchesFilters(entry, filters.value)
  })
})

/** The typed text, when it is not a catalogue entry. */
const custom = computed(() => {
  const typed = query.value.trim()
  if (!typed || byId.value.has(typed) || props.exclude.includes(typed)) return ''
  if (matches.value.some((entry) => entry.id === typed)) return ''
  return typed
})

const age = computed(() => {
  const count = `${catalog.value.models.length} models`
  const first = Object.entries(catalog.value.fetched)[0]
  if (!first) return count
  const [source, when] = first
  return `${count} · ${source}, ${day(utcStamp(when)) ?? 'unknown'}`
})

function pillClass(on: boolean): string {
  return on
    ? 'bg-secondary text-secondary-foreground'
    : 'text-muted-foreground hover:text-foreground'
}

function describe(entry: BenchmarkModel): string {
  const parts: string[] = []
  if (entry.context_length) parts.push(`${Math.round(entry.context_length / 1000)}k ctx`)
  const price = entry.pricing?.prompt
  if (price) {
    const perMillion = Number(price) * 1_000_000
    if (Number.isFinite(perMillion)) {
      parts.push(perMillion === 0 ? 'free' : `$${trim(perMillion)}/M in`)
    }
  }
  return parts.length ? ` · ${parts.join(' · ')}` : ''
}

function trim(value: number): string {
  return value >= 10 ? value.toFixed(0) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

function write(next: string[]): void {
  if (props.multiple) {
    // An empty list means not set.
    emit('update:modelValue', next.length ? next : undefined)
    return
  }
  emit('update:modelValue', next[0])
}

function toggle(id: string): void {
  const current = selected.value
  write(current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
}

function choose(id: string): void {
  if (props.multiple) {
    toggle(id)
    query.value = ''
    return
  }
  write([id])
  open.value = false
}

/** Enter picks the first match, or the typed name. */
function takeFirst(): void {
  const first = movingMatches.value[0]?.[1] ?? shown.value[0]?.id ?? custom.value
  if (first) choose(first)
}

async function doRefresh(): Promise<void> {
  if (!props.connectionId) return
  await refresh(props.connectionId)
}
</script>
