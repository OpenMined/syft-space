<template>
  <Card class="text-center py-12">
    <CardContent class="space-y-6">
      <!-- Icon -->
      <div class="mx-auto w-16 h-16 bg-muted rounded-full flex items-center justify-center">
        <slot name="icon">
          <component :is="defaultIcon" class="w-8 h-8 icon-muted" />
        </slot>
      </div>

      <!-- Title -->
      <div>
        <h3 class="heading-4 mb-2">
          <slot name="title">{{ title }}</slot>
        </h3>

        <!-- Description -->
        <p class="body-sm max-w-sm mx-auto">
          <slot name="description">{{ description }}</slot>
        </p>
      </div>

      <!-- Actions -->
      <div v-if="$slots.actions" class="flex items-center justify-center gap-3">
        <slot name="actions" />
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { type LucideIcon } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'

defineProps<{
  title?: string
  description?: string
  defaultIcon?: LucideIcon
}>()
</script>
