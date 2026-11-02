<template>
  <div class="space-y-2">
    <div class="flex gap-2">
      <Input
        :id="id"
        v-model="tagInput"
        @keydown.enter.prevent="addTag(tagInput)"
        placeholder="e.g., legal, medical, research"
        class="flex-1"
      />
      <Button
        type="button"
        variant="outline"
        :disabled="!tagInput.trim()"
        @click="addTag(tagInput)"
      >
        <Plus class="h-4 w-4" />
      </Button>
    </div>

    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-xs text-muted-foreground">Popular:</span>
      <Button
        v-for="suggestion in POPULAR_TAGS"
        :key="suggestion"
        type="button"
        variant="ghost"
        size="sm"
        class="h-6 px-2 text-xs"
        :disabled="modelValue.includes(suggestion)"
        @click="addTag(suggestion)"
      >
        {{ suggestion }}
      </Button>
    </div>

    <div v-if="modelValue.length > 0" class="flex flex-wrap gap-2 mt-3">
      <Badge v-for="(tag, index) in modelValue" :key="tag" variant="secondary" class="px-3 py-1">
        {{ tag }}
        <button
          type="button"
          class="ml-2 hover:text-destructive transition-colors"
          :aria-label="`Remove ${tag}`"
          @click="removeTag(index)"
        >
          <X class="h-3 w-3" />
        </button>
      </Badge>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Plus, X } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const POPULAR_TAGS = ['legal', 'medical', 'research', 'finance', 'education', 'news', 'technical']

const props = defineProps<{
  modelValue: string[]
  id?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [tags: string[]]
}>()

const tagInput = ref('')

const addTag = (raw: string) => {
  const tag = raw.trim().toLowerCase()
  if (!tag || props.modelValue.includes(tag)) return
  emit('update:modelValue', [...props.modelValue, tag])
  tagInput.value = ''
}

const removeTag = (index: number) => {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== index),
  )
}
</script>
