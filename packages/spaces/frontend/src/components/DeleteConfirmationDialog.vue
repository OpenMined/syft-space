<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[500px]">
      <DialogHeader>
        <DialogTitle>Delete {{ itemType }}</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ itemName }}"? This action cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <!-- Blocked: has active dependencies -->
      <div v-if="dependencies && dependencies.length > 0" class="py-2">
        <div
          class="flex items-start gap-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3"
        >
          <AlertTriangle class="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p class="text-sm font-medium text-amber-900 dark:text-amber-300">
              Cannot delete — in use by {{ dependencies.length }} {{ dependencyType
              }}{{ dependencies.length !== 1 ? 's' : '' }}
            </p>
            <p class="text-xs text-amber-700 dark:text-amber-400 mt-1">
              Remove this {{ itemType.toLowerCase() }} from the following
              {{ dependencyType.toLowerCase() }}{{ dependencies.length !== 1 ? 's' : '' }} first:
            </p>
            <ul class="mt-2 space-y-1">
              <li
                v-for="dep in dependencies"
                :key="dep"
                class="text-xs font-medium text-amber-800 dark:text-amber-300"
              >
                • {{ dep }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="handleCancel"> Cancel </Button>
        <Button
          v-if="!dependencies || dependencies.length === 0"
          variant="destructive"
          :disabled="isDeleting"
          @click="handleConfirm"
        >
          <template v-if="isDeleting">Deleting...</template>
          <template v-else>Delete {{ itemType }}</template>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle } from 'lucide-vue-next'

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
  dependencyType: 'API',
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

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
  emit('update:open', false)
}
</script>
