<template>
  <div class="space-y-1.5">
    <Popover v-model:open="open">
      <!-- The anchor is the whole control, not the part that opens the list:
           that is what the popover takes its width from, and a list narrower
           than the field it belongs to reads as a different control. -->
      <PopoverAnchor as-child>
        <div
          class="flex min-h-9 w-full flex-wrap items-center gap-1 rounded-md border bg-transparent px-3 py-1.5 text-sm shadow-xs transition-[color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50"
          :class="warn ? 'border-amber-500' : 'border-input'"
        >
          <!-- Several models are chips, one is a line of text: a single model
               shown as a chip reads as "one of many".

               Each chip's remove control is a button of its own and sits
               OUTSIDE the one that opens the list — nested inside it, a click
               would reach the button around it and open the picker. -->
          <template v-if="multiple">
            <Badge
              v-for="id in selected"
              :key="id"
              variant="secondary"
              class="gap-1 font-normal"
              :title="id"
            >
              {{ label(id) }}
              <button
                type="button"
                :aria-label="`Remove ${label(id)}`"
                class="cursor-pointer rounded-xs opacity-60 hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-1"
                @click="toggle(id)"
              >
                <X class="size-3" />
              </button>
            </Badge>
          </template>

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
              <span v-else-if="!multiple" class="truncate text-foreground" :title="selected[0]">
                {{ label(selected[0]!) }}
              </span>
              <span v-else class="text-muted-foreground">{{ addLabel }}</span>

              <ChevronsUpDown class="size-4 shrink-0 opacity-50" />
            </button>
          </PopoverTrigger>
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

        <!-- The vendors come from the catalogue, not from a list on this side:
             a benchmark whose provider adds a vendor gets it here the same day. -->
        <div
          v-if="catalog.vendors.length"
          class="flex flex-wrap gap-1 border-b border-border/50 px-2 py-2"
        >
          <button
            type="button"
            class="rounded-md px-1.5 py-0.5 text-[11px] transition-colors"
            :class="
              vendor === ''
                ? 'bg-secondary text-secondary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            "
            @click="vendor = ''"
          >
            All
          </button>
          <button
            v-for="name in catalog.vendors"
            :key="name"
            type="button"
            class="rounded-md px-1.5 py-0.5 text-[11px] transition-colors"
            :class="
              vendor === name
                ? 'bg-secondary text-secondary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            "
            @click="vendor = vendor === name ? '' : name"
          >
            {{ name }}
          </button>
        </div>

        <div
          class="flex flex-wrap gap-1 border-b border-border/50 px-2 py-2"
          data-testid="model-filters"
        >
          <button
            v-for="chip in MODEL_FILTERS"
            :key="chip.value"
            type="button"
            class="rounded-md px-1.5 py-0.5 text-[11px] transition-colors"
            :class="
              filters.includes(chip.value)
                ? 'bg-secondary text-secondary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            "
            :title="chip.help"
            :aria-pressed="filters.includes(chip.value)"
            @click="filters = toggleFilter(filters, chip.value)"
          >
            {{ chip.label }}
          </button>
        </div>

        <div class="max-h-72 overflow-y-auto py-1">
          <p v-if="loading" class="px-3 py-6 text-center text-xs text-muted-foreground">
            Loading the catalogue…
          </p>

          <template v-else>
            <!-- A name that means a different model every few months. Offered
                 as the convenient way to say "the current one", but what is
                 stored is the model it means today. -->
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
                  <span class="truncate text-sm text-foreground">{{ modelName(entry.id, entry) }}</span>
                </span>
                <span class="block truncate pl-5 text-[11px] text-muted-foreground">
                  {{ entry.id }}{{ describe(entry) }}
                </span>
              </span>
              <span class="flex shrink-0 items-center gap-1">
                <Badge
                  v-if="webSearchOf(entry) === 'native'"
                  variant="outline"
                  class="font-normal"
                  title="Has built-in web search."
                  >Web</Badge
                >
                <Badge
                  v-else-if="webSearchOf(entry) === 'plugin'"
                  variant="outline"
                  class="font-normal"
                  title="Searches through the OpenRouter web plugin."
                  >Web plugin</Badge
                >
                <Badge
                  v-if="!takesTemperature(entry)"
                  variant="outline"
                  class="font-normal"
                  title="Takes no temperature setting."
                  >No temperature</Badge
                >
                <Badge v-if="entry.local" variant="outline" class="font-normal">local</Badge>
                <Badge v-if="entry.retires_on" variant="outline" class="font-normal">
                  retires {{ entry.retires_on }}
                </Badge>
              </span>
            </button>

            <p v-if="hidden > 0" class="px-3 py-1.5 text-[11px] text-muted-foreground">
              and {{ hidden }} more — narrow the search
            </p>

            <!-- The catalogue is not a whitelist: a model released this
                 morning is in no snapshot. -->
            <button
              v-if="custom"
              type="button"
              class="flex w-full items-start justify-between gap-3 border-t border-border/50 px-3 py-1.5 text-left hover:bg-accent/50"
              @click="choose(custom!)"
            >
              <span class="min-w-0">
                <span class="block truncate text-sm text-foreground">Use “{{ custom }}”</span>
                <span class="block truncate text-[11px] text-muted-foreground">
                  not in the catalogue — it will be sent exactly as written
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

    <!-- A stored value the catalogue has never heard of: it may be newer than
         the snapshot, and it may be a typo. -->
    <p v-if="unknown.length" class="text-xs text-muted-foreground">
      Not in the catalogue: {{ unknown.join(', ') }}. It will be sent as written.
    </p>
  </div>
</template>

<script setup lang="ts">
/**
 * Choosing models by picking rather than by spelling: a typo in a model name is
 * found by the provider, not by the form, and costs a paid run.
 *
 * Nothing here knows which field it is drawing. The benchmark marks a field
 * with `catalog: "models"` and this fetches that catalogue — the same rule by
 * which `/schema` describes fields rather than the form knowing them by name.
 *
 * What the picker shows and what it stores differ for `~vendor/thing-latest`
 * names: it stores the model such a name means today, because a measurement
 * recorded under a moving name cannot be repeated.
 */
import { computed, ref, watch } from 'vue'
import { Check, ChevronsUpDown, Search, X } from 'lucide-vue-next'

import { Badge } from '@/components/ui/badge'
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  MODEL_FILTERS,
  matchesFilters,
  modelName,
  takesTemperature,
  toggleFilter,
  webSearchOf,
} from '@/components/benchmark/setup/setupForm'
import type { ModelFilter } from '@/components/benchmark/setup/setupForm'
import { useModelCatalog } from '@/composables/useModelCatalog'
import type { BenchmarkModel } from '@/api/types'

// The rest are a line saying how many: three hundred rows in a popover are
// slower to scroll than to narrow.
const SHOWN = 80

const props = withDefaults(
  defineProps<{
    modelValue?: string | string[]
    /** A panel of judges and a list of models under test take several. */
    multiple?: boolean
    /** Which benchmark's catalogue. Without it the picker still takes a typed name. */
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

// Loaded with the page: the chosen models are shown by their catalogue names.
// The cache makes every picker on a page share one request.
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

/** Chosen values the catalogue does not know — newer than it, or a typo. */
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
  // A moving name has no capabilities of its own; the model it means today does.
  if (filters.value.length) {
    return Object.entries(catalog.value.pins).filter(([name, target]) => {
      const entry = byId.value.get(target)
      return (
        !!entry &&
        !props.exclude.includes(target) &&
        matchesFilters(entry, filters.value) &&
        (!needle.value || name.toLowerCase().includes(needle.value))
      )
    })
  }
  return Object.entries(catalog.value.pins).filter(
    ([name, target]) =>
      !props.exclude.includes(target) &&
      (!needle.value || name.toLowerCase().includes(needle.value)),
  )
})

/** The typed text, when it is not already an entry — offered as it stands. */
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
  return `${count} · ${source}, ${when ? when.slice(0, 10) : 'unknown'}`
})

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
    // An empty list reads as "not set here", as everywhere else in this form.
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

/** Enter takes the obvious one: the first match, or the typed name. */
function takeFirst(): void {
  const first = movingMatches.value[0]?.[1] ?? shown.value[0]?.id ?? custom.value
  if (first) choose(first)
}

async function doRefresh(): Promise<void> {
  if (!props.connectionId) return
  await refresh(props.connectionId)
}
</script>
