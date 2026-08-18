<template>
  <div class="space-y-2">
    <!-- Normal mode: searchable combobox -->
    <template v-if="!showManualInput">
      <Popover v-model:open="open">
        <PopoverTrigger as-child>
          <Button
            variant="outline"
            role="combobox"
            :aria-expanded="open"
            :disabled="disabled || isLoading"
            class="w-full justify-between font-normal"
          >
            <span v-if="isLoading" class="flex items-center text-muted-foreground">
              <Loader2 class="h-4 w-4 animate-spin mr-2" />
              Loading models...
            </span>
            <span v-else-if="selectedModel" class="truncate">
              {{ selectedModel.name || selectedModel.id }}
            </span>
            <span v-else class="text-muted-foreground">{{ placeholder }}</span>
            <ChevronsUpDown class="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent class="w-[--reka-popover-trigger-width] p-0" align="start">
          <Command>
            <CommandInput placeholder="Search models..." />
            <CommandEmpty>
              <span v-if="error" class="text-destructive">{{ error }}</span>
              <span v-else>No models found.</span>
            </CommandEmpty>
            <CommandList>
              <CommandGroup>
                <CommandItem
                  v-for="model in models"
                  :key="model.id"
                  :value="model.name || model.id"
                  @select="handleSelect(model)"
                >
                  <Check
                    :class="['mr-2 h-4 w-4', modelValue === model.id ? 'opacity-100' : 'opacity-0']"
                  />
                  <div class="flex flex-col min-w-0">
                    <span class="truncate">{{ model.name || model.id }}</span>
                    <span
                      v-if="model.name && model.name !== model.id"
                      class="text-xs text-muted-foreground truncate"
                    >
                      {{ model.id }}
                    </span>
                  </div>
                </CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </template>

    <!-- Manual input fallback -->
    <template v-else>
      <Input
        :model-value="modelValue"
        @update:model-value="$emit('update:modelValue', String($event))"
        placeholder="Enter model ID (e.g., gpt-4o)"
        class="w-full font-mono text-sm"
      />
    </template>

    <!-- Error with fallback toggle -->
    <div v-if="error && !showManualInput" class="flex items-center gap-2">
      <p class="text-sm text-destructive flex-1">{{ error }}</p>
      <Button variant="link" size="sm" class="text-xs px-0 h-auto" @click="showManualInput = true">
        Enter model ID manually
      </Button>
    </div>
    <div v-if="showManualInput" class="flex items-center gap-2">
      <p class="text-sm text-muted-foreground flex-1">Entering model ID manually</p>
      <Button variant="link" size="sm" class="text-xs px-0 h-auto" @click="showManualInput = false">
        Back to model list
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Check, ChevronsUpDown, Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { ProviderModelItem } from '@/api/types'

const props = withDefaults(
  defineProps<{
    modelValue: string
    models: ProviderModelItem[]
    isLoading?: boolean
    error?: string | null
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    isLoading: false,
    error: null,
    disabled: false,
    placeholder: 'Select a model',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const showManualInput = ref(false)

const selectedModel = computed(() => {
  if (!props.modelValue) return null
  return props.models.find((m) => m.id === props.modelValue) ?? null
})

const handleSelect = (model: ProviderModelItem) => {
  emit('update:modelValue', model.id)
  open.value = false
}
</script>
