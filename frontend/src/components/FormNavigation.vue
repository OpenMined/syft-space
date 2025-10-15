<template>
  <div class="flex justify-between items-center pt-6 border-t border-gray-200">
    <Button v-if="!isFirstStep" variant="outline" @click="$emit('previous')" :disabled="loading">
      <ChevronLeft class="h-4 w-4 mr-2" />
      Previous
    </Button>
    <div v-else></div>
    <!-- Spacer for alignment -->

    <div class="flex gap-3">
      <Button
        v-if="showSaveDraft"
        variant="outline"
        @click="$emit('save-draft')"
        :disabled="loading"
      >
        <Save class="h-4 w-4 mr-2" />
        Save Draft
      </Button>

      <Button v-if="!isLastStep" @click="$emit('next')" :disabled="!canProceed || loading">
        Next
        <ChevronRight class="h-4 w-4 ml-2" />
      </Button>

      <Button v-else @click="$emit('submit')" :disabled="!canProceed || loading">
        <span v-if="loading" class="flex items-center">
          <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
          {{ submitLoadingText }}
        </span>
        <span v-else class="flex items-center">
          <Check class="h-4 w-4 mr-2" />
          {{ submitText }}
        </span>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChevronLeft, ChevronRight, Save, Check } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

interface Props {
  isFirstStep: boolean
  isLastStep: boolean
  canProceed: boolean
  loading?: boolean
  showSaveDraft?: boolean
  submitText?: string
  submitLoadingText?: string
}

interface Emits {
  (e: 'previous'): void
  (e: 'next'): void
  (e: 'submit'): void
  (e: 'save-draft'): void
}

withDefaults(defineProps<Props>(), {
  loading: false,
  showSaveDraft: true,
  submitText: 'Create Endpoint',
  submitLoadingText: 'Creating...',
})

defineEmits<Emits>()
</script>
