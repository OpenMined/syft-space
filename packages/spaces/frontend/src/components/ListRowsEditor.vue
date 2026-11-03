<template>
  <div class="border-input rounded-md border">
    <div class="max-h-[158px] min-h-[112px] overflow-y-auto">
      <input
        v-for="(row, index) in rows"
        :key="index"
        :ref="(el) => setRowRef(index, el)"
        :value="row"
        :placeholder="placeholder"
        class="w-full bg-transparent px-3 py-1.5 text-sm outline-none focus:bg-accent"
        :class="{ 'bg-accent/50': selected === index }"
        @input="onInput(index, $event)"
        @focus="selected = index"
        @blur="onBlur(index)"
        @paste="onPaste(index, $event)"
      />
    </div>
    <div class="border-input flex items-center gap-1 border-t px-1 py-0.5">
      <button
        type="button"
        class="text-muted-foreground hover:text-foreground hover:bg-accent rounded px-2 py-0.5 text-base leading-none"
        :aria-label="`Add ${label}`"
        @click="addRow"
      >
        +
      </button>
      <span class="bg-border h-4 w-px" />
      <button
        type="button"
        class="text-muted-foreground hover:text-foreground hover:bg-accent rounded px-2 py-0.5 text-base leading-none disabled:opacity-40 disabled:hover:bg-transparent"
        :disabled="rows.length <= 1 && rows[0] === ''"
        :aria-label="`Remove ${label}`"
        @click="removeRow"
      >
        −
      </button>
    </div>
  </div>
  <p v-if="hint" class="text-muted-foreground text-xs">{{ hint }}</p>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

// A fixed-height list of editable text rows with a +/- toolbar. Rows are
// emitted exactly as typed and only normalized on blur, so the person is
// never fought mid-keystroke. The parent decides what the rows become.
const props = withDefaults(
  defineProps<{
    modelValue: string[]
    label: string
    placeholder?: string
    // Pasted text containing this separator (or newlines) fills one row per value.
    separator?: string
  }>(),
  { placeholder: '', separator: ',' },
)

const emit = defineEmits<{
  'update:modelValue': [rows: string[]]
}>()

// An empty list shows one blank row so there is always somewhere to type.
const rows = computed(() => (props.modelValue.length > 0 ? props.modelValue : ['']))
const selected = ref(0)
const hint = ref('')
const rowRefs = new Map<number, HTMLInputElement>()

const setRowRef = (index: number, el: unknown) => {
  if (el instanceof HTMLInputElement) rowRefs.set(index, el)
  else rowRefs.delete(index)
}

/** Trailing slashes are insignificant in every list we store (URLs), so `foo.com/` == `foo.com`. */
const normalize = (value: string) => value.trim().replace(/\/+$/, '')

const update = (next: string[]) => emit('update:modelValue', next)

const onInput = (index: number, event: Event) => {
  const next = [...rows.value]
  next[index] = (event.target as HTMLInputElement).value
  update(next)
}

const onBlur = (index: number) => {
  const next = [...rows.value]
  const normalized = normalize(next[index] ?? '')
  const isDuplicate =
    normalized !== '' && next.some((r, i) => i !== index && normalize(r) === normalized)
  if (isDuplicate) {
    next.splice(index, 1)
    hint.value = 'Already added — that duplicate was removed.'
  } else {
    next[index] = normalized
    hint.value = ''
  }
  update(next)
}

const onPaste = (index: number, event: ClipboardEvent) => {
  const text = event.clipboardData?.getData('text') ?? ''
  if (!text.includes(props.separator) && !text.includes('\n')) return
  event.preventDefault()
  const pasted = text
    .split(new RegExp(`[${props.separator}\n]`))
    .map(normalize)
    .filter(Boolean)
  const next = [...rows.value]
  next.splice(index, 1, ...pasted)
  selected.value = Math.min(index + pasted.length - 1, next.length - 1)
  update(next)
}

const addRow = async () => {
  const next = [...rows.value, '']
  selected.value = next.length - 1
  update(next)
  await nextTick()
  rowRefs.get(selected.value)?.focus()
}

/** Remove the selected row, falling back to the last one. */
const removeRow = async () => {
  const next = [...rows.value]
  const index = Math.min(selected.value, next.length - 1)
  next.splice(index, 1)
  selected.value = Math.max(0, Math.min(index, next.length - 1))
  hint.value = ''
  update(next)
  await nextTick()
  rowRefs.get(selected.value)?.focus()
}
</script>
