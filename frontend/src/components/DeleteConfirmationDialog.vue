<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Delete {{ itemType }}</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ itemName }}"? This action cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <div v-if="dependencies && dependencies.length > 0" class="py-4">
        <div class="space-y-4">
          <div class="bg-destructive/10 border border-destructive/20 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-destructive font-semibold body-sm mb-2">
                  This {{ itemType.toLowerCase() }} has {{ dependencies.length }} dependent
                  {{ dependencyType }}{{ dependencies.length !== 1 ? 's' : '' }} that will be deleted:
                </p>
                <p class="text-destructive/80 body-sm mb-3">
                  Check each {{ dependencyType }} to confirm deletion
                </p>
                <div class="space-y-2">
                  <div
                    v-for="dep in dependencies"
                    :key="dep"
                    class="flex items-center gap-3 p-2.5 bg-background rounded border border-destructive/20 cursor-pointer hover:bg-muted/50 transition-colors"
                    @click="toggleDependency(dep)"
                  >
                    <div
                      class="w-4 h-4 rounded-sm border flex items-center justify-center shrink-0 transition-colors"
                      :class="
                        checkedDependencies.includes(dep)
                          ? 'bg-primary border-primary text-primary-foreground'
                          : 'border-input bg-background'
                      "
                    >
                      <Check v-if="checkedDependencies.includes(dep)" class="w-3 h-3" />
                    </div>
                    <span class="flex-1 flex items-center justify-between">
                      <span
                        class="body-sm font-medium text-foreground"
                        :class="{ 'line-through opacity-60': checkedDependencies.includes(dep) }"
                      >
                        {{ dep }}
                      </span>
                      <span class="body-sm text-destructive">Will be deleted</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="handleCancel"> Cancel </Button>
        <Button
          variant="destructive"
          @click="handleConfirm"
          :disabled="!allDependenciesChecked || isDeleting"
        >
          <template v-if="isDeleting">Deleting...</template>
          <template v-else>
            {{
              dependencies && dependencies.length > 0
                ? `Delete ${itemType} & ${dependencies.length} ${dependencyType}${dependencies.length !== 1 ? 's' : ''}`
                : `Delete ${itemType}`
            }}
          </template>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Check } from 'lucide-vue-next'

interface Props {
  open?: boolean
  itemType: string
  itemName: string
  dependencies?: string[]
  dependencyType?: string
  isDeleting?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  dependencies: () => [],
  dependencyType: 'endpoint',
  isDeleting: false,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  confirm: []
  cancel: []
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const checkedDependencies = ref<string[]>([])

const allDependenciesChecked = computed(() => {
  if (!props.dependencies || props.dependencies.length === 0) return true
  return props.dependencies.every((dep) => checkedDependencies.value.includes(dep))
})

const toggleDependency = (dep: string) => {
  const index = checkedDependencies.value.indexOf(dep)
  if (index > -1) {
    checkedDependencies.value.splice(index, 1)
  } else {
    checkedDependencies.value.push(dep)
  }
}

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  checkedDependencies.value = []
  emit('cancel')
  emit('update:open', false)
}

// Reset checked dependencies when dialog opens
watch(
  () => props.open,
  (newValue) => {
    if (newValue) {
      checkedDependencies.value = []
    }
  },
)
</script>
