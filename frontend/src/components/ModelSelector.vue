<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="space-y-2">
      <h4 class="text-base font-medium text-gray-900">{{ title }}</h4>
      <p class="text-sm text-gray-600">{{ description }}</p>
    </div>

    <!-- Model List -->
    <RadioGroup :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
      <div class="space-y-3">
        <!-- Existing Models -->
        <div
          v-for="model in mockModels"
          :key="model.id"
          class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
          :class="modelValue === model.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'"
          @click="$emit('update:modelValue', model.id)"
        >
          <RadioGroupItem :value="model.id" :id="`${idPrefix}-${model.id}`" />
          <Label
            :for="`${idPrefix}-${model.id}`"
            class="flex items-center gap-3 cursor-pointer flex-1"
          >
            <div
              :class="[
                'p-2 rounded',
                model.type === 'vllm'
                  ? 'bg-purple-100'
                  : model.type === 'ollama'
                    ? 'bg-orange-100'
                    : 'bg-indigo-100',
              ]"
            >
              <IntegrationIcon :name="model.type" class="h-5 w-5" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ model.name }}</span>
                <Badge variant="secondary" class="text-xs">{{ model.type }}</Badge>
                <Badge
                  variant="outline"
                  :class="
                    model.status === 'running'
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-gray-50 text-gray-600 border-gray-200'
                  "
                  class="text-xs"
                >
                  {{ model.status }}
                </Badge>
              </div>
              <p class="text-sm text-gray-600 mt-1">{{ model.description }}</p>
            </div>
          </Label>
        </div>

        <!-- Create New Model Option (outside radio group) -->
        <div
          class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50 border-gray-200"
          @click="handleCreateModel"
        >
          <!-- Spacer to maintain alignment with radio button items -->
          <div class="w-4 h-4"></div>
          <div class="flex items-center gap-3 cursor-pointer flex-1">
            <div class="p-2 bg-gray-100 rounded">
              <Plus class="h-5 w-5 text-gray-600" />
            </div>
            <div class="flex-1">
              <span class="font-medium">Create New Model</span>
              <p class="text-sm text-gray-600 mt-1">Set up a new AI model for your endpoint</p>
            </div>
          </div>
        </div>
      </div>
    </RadioGroup>
  </div>
</template>

<script setup lang="ts">
import { Plus } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import { mockModels } from '@/stores/models'

interface Props {
  modelValue: string
  title?: string
  description?: string
  idPrefix?: string
}

withDefaults(defineProps<Props>(), {
  title: 'AI Model',
  description: 'Select an AI model',
  idPrefix: 'model',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'create-model': []
}>()

const handleCreateModel = () => {
  emit('update:modelValue', '')
  emit('create-model')
}
</script>
