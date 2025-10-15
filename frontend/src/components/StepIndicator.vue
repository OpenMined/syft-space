<template>
  <div class="flex items-center justify-center space-x-4 mb-8">
    <div v-for="(step, index) in steps" :key="step.id" class="flex items-center">
      <!-- Step Circle -->
      <div
        :class="getStepClasses(step.id)"
        class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors"
      >
        {{ step.id }}
      </div>

      <!-- Step Title -->
      <div class="ml-3 text-sm">
        <div :class="getStepTextClasses(step.id)" class="font-medium">
          {{ step.title }}
        </div>
        <div v-if="step.description" class="text-gray-500 text-xs">
          {{ step.description }}
        </div>
      </div>

      <!-- Connector Line -->
      <div
        v-if="index < steps.length - 1"
        :class="getConnectorClasses(step.id)"
        class="w-8 h-px mx-4 transition-colors"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Step {
  id: number
  title: string
  description?: string
}

interface Props {
  steps: Step[]
  currentStep: number
}

const props = defineProps<Props>()

const getStepClasses = (stepId: number) =>
  computed(() => ({
    'bg-blue-600 text-white border-blue-600': props.currentStep >= stepId,
    'bg-gray-200 text-gray-500 border-gray-200': props.currentStep < stepId,
  }))

const getStepTextClasses = (stepId: number) =>
  computed(() => ({
    'text-blue-600': props.currentStep >= stepId,
    'text-gray-500': props.currentStep < stepId,
  }))

const getConnectorClasses = (stepId: number) =>
  computed(() => ({
    'bg-blue-600': props.currentStep > stepId,
    'bg-gray-200': props.currentStep <= stepId,
  }))
</script>
