<script setup lang="ts">
/**
 * One provider role: what it sends and where, its address, and its key.
 *
 * The address is part of the whole-document save the page around this does;
 * the key is not — it is set or cleared immediately, one call each, because
 * it never travels back to be edited in place.
 */
import { computed, ref } from 'vue'
import { ArrowUpRight, HardDrive } from 'lucide-vue-next'
import InfoTip from '@/components/benchmark/InfoTip.vue'
import { hostOf, type KeySource } from '@/components/benchmark/modelAccess'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

const props = defineProps<{
  label: string
  tip: string
  /** What the role sends; empty for a role that sends nothing itself. */
  sends: string
  url: string
  /** Shown in an empty address box: what a blank address resolves to. */
  placeholder: string
  /** The address the role actually calls. */
  target: string
  local: boolean
  keySet: boolean
  keySource: KeySource
  busy: boolean
}>()

const KEY_LABELS: Record<KeySource, string> = {
  own: 'Key set',
  inherited: 'Inherited key',
  none: 'No key',
}

const emit = defineEmits<{
  'update:url': [string]
  saveKey: [string]
  clearKey: []
}>()

const keyInput = ref('')

const whereTip = computed(() => {
  const host = hostOf(props.target) || 'the default address'
  return props.local
    ? `Sent to ${host}, on this machine or its Docker network.`
    : `Sent to ${host}, outside this machine.`
})

function saveKey() {
  if (!keyInput.value) return
  emit('saveKey', keyInput.value)
  keyInput.value = ''
}
</script>

<template>
  <div class="border border-border/50 rounded-md p-3 space-y-2">
    <div class="flex items-start justify-between gap-4">
      <div class="space-y-0.5">
        <p class="flex items-center gap-1.5 text-sm font-medium text-foreground">
          {{ label }}
          <InfoTip :text="tip" />
        </p>
        <p v-if="sends" class="text-xs text-muted-foreground">
          Sends: <span class="text-foreground">{{ sends }}</span>
        </p>
      </div>
      <div class="flex items-center gap-1.5 shrink-0">
        <TooltipProvider v-if="sends">
          <Tooltip>
            <TooltipTrigger as-child>
              <span
                class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md cursor-default"
                :class="
                  local
                    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                    : 'bg-sky-500/10 text-sky-700 dark:text-sky-400'
                "
                data-testid="locality"
              >
                <component :is="local ? HardDrive : ArrowUpRight" class="h-3 w-3" />
                {{ local ? 'Stays local' : 'Leaves machine' }}
              </span>
            </TooltipTrigger>
            <TooltipContent class="max-w-64">{{ whereTip }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <span
          class="text-xs px-2 py-1 rounded-md"
          :class="
            keySource === 'own'
              ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
              : 'bg-muted text-muted-foreground'
          "
          :title="keySource === 'inherited' ? 'Uses the key of the role it follows.' : undefined"
        >
          {{ KEY_LABELS[keySource] }}
        </span>
      </div>
    </div>

    <div class="grid sm:grid-cols-2 gap-3">
      <div class="space-y-1">
        <Label class="text-xs">Address</Label>
        <Input
          :model-value="url"
          :placeholder="placeholder || 'default'"
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
