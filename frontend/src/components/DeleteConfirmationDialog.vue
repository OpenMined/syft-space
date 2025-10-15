<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Delete {{ itemType }}</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ itemName }}"? This action cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <!-- Dependencies Warning -->
      <div v-if="dependencies && dependencies.length > 0" class="py-4">
        <div class="space-y-4">
          <div class="bg-red-50 border border-red-200 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-red-900 font-semibold text-sm mb-2">
                  This {{ itemType.toLowerCase() }} has {{ dependencies.length }} dependent
                  {{ dependencyType }}{{ dependencies.length !== 1 ? 's' : '' }} that will be
                  deleted:
                </p>
                <p class="text-red-800 text-xs mb-3">
                  Check each {{ dependencyType }} to confirm deletion
                </p>
                <div class="space-y-2">
                  <div
                    v-for="dependency in dependencies"
                    :key="dependency.id"
                    class="flex items-center gap-3 p-2.5 bg-white rounded border border-red-200"
                  >
                    <input
                      type="checkbox"
                      :id="`dependency-${dependency.id}`"
                      :checked="checkedDependencies.includes(dependency.id)"
                      @change="() => toggleDependency(dependency.id)"
                      class="w-4 h-4 text-red-600 bg-white border-red-400 rounded focus:ring-red-500 focus:ring-2"
                    />
                    <label
                      :for="`dependency-${dependency.id}`"
                      class="flex-1 cursor-pointer flex items-center justify-between"
                    >
                      <span class="text-sm font-medium text-gray-900">
                        {{ dependency.name }}
                      </span>
                      <span class="text-xs text-red-600"> Will be deleted </span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="handleCancel"> Cancel </Button>
        <Button variant="destructive" @click="handleConfirm" :disabled="!canDelete">
          {{ deleteButtonText }}
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

interface Dependency {
  id: string
  name: string
}

interface Props {
  open?: boolean
  itemType: string
  itemName: string
  dependencies?: Dependency[]
  dependencyType?: string
}

interface Emits {
  (e: 'update:open', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  dependencies: () => [],
  dependencyType: 'item',
})

const emit = defineEmits<Emits>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const checkedDependencies = ref<string[]>([])

const canDelete = computed(() => {
  if (!props.dependencies || props.dependencies.length === 0) return true
  return props.dependencies.length === checkedDependencies.value.length
})

const deleteButtonText = computed(() => {
  if (!props.dependencies || props.dependencies.length === 0) {
    return `Delete ${props.itemType}`
  }
  return `Delete ${props.itemType} & ${props.dependencies.length} ${props.dependencyType}${props.dependencies.length !== 1 ? 's' : ''}`
})

const toggleDependency = (dependencyId: string) => {
  const index = checkedDependencies.value.indexOf(dependencyId)
  if (index > -1) {
    checkedDependencies.value.splice(index, 1)
  } else {
    checkedDependencies.value.push(dependencyId)
  }
}

const handleConfirm = () => {
  emit('confirm')
  handleCancel() // Reset state
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
