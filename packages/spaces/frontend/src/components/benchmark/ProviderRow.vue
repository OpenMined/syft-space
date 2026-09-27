<script setup lang="ts">
/**
 * One provider role: its address, and its key.
 *
 * The address is part of the whole-document save the page around this does;
 * the key is not — it is set or cleared immediately, one call each, because
 * it never travels back to be edited in place.
 */
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const props = defineProps<{
  label: string
  help: string
  url: string
  urlDefault: string
  keySet: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  'update:url': [string]
  saveKey: [string]
  clearKey: []
}>()

const keyInput = ref('')

function saveKey() {
  if (!keyInput.value) return
  emit('saveKey', keyInput.value)
  keyInput.value = ''
}
</script>

<template>
  <div class="border border-border/50 rounded-md p-3 space-y-2">
    <div class="flex items-center justify-between gap-4">
      <div>
        <p class="text-sm font-medium text-foreground">{{ label }}</p>
        <p class="text-xs text-muted-foreground">{{ help }}</p>
      </div>
      <span
        class="text-xs px-2 py-1 rounded-md shrink-0"
        :class="
          keySet
            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
            : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
        "
      >
        {{ keySet ? 'Key is set' : 'No key' }}
      </span>
    </div>

    <div class="grid sm:grid-cols-2 gap-3">
      <div class="space-y-1">
        <Label class="text-xs">Address</Label>
        <Input
          :model-value="url"
          :placeholder="urlDefault || 'default'"
          class="h-8 text-xs"
          @update:model-value="(v) => emit('update:url', String(v))"
        />
      </div>
      <div class="space-y-1">
        <Label class="text-xs">Key</Label>
        <div class="flex gap-1.5">
          <Input
            v-model="keyInput"
            type="password"
            :placeholder="keySet ? 'Stored — leave blank to keep it' : ''"
            class="h-8 text-xs"
            :disabled="props.busy"
          />
          <Button
            v-if="keyInput"
            size="sm"
            variant="outline"
            class="h-8 px-2 text-xs"
            :disabled="props.busy"
            @click="saveKey"
          >
            Save
          </Button>
          <Button
            v-else-if="keySet"
            size="sm"
            variant="ghost"
            class="h-8 px-2 text-xs text-destructive hover:text-destructive"
            :disabled="props.busy"
            @click="emit('clearKey')"
          >
            Clear
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
