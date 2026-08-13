<template>
  <Card class="py-12 text-center">
    <CardContent class="space-y-6">
      <!-- A custom visual (via #icon slot) stands on its own; the default
           `icon` prop sits in a muted circle. -->
      <div v-if="$slots.icon" class="flex justify-center">
        <slot name="icon" />
      </div>
      <div
        v-else-if="icon"
        class="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted"
      >
        <component :is="icon" class="h-8 w-8 text-muted-foreground" />
      </div>

      <!-- Title -->
      <div>
        <h3 class="heading-4 mb-2">
          <slot name="title">{{ title }}</slot>
        </h3>

        <!-- Description -->
        <p class="body-sm mx-auto max-w-sm text-muted-foreground">
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
  icon?: LucideIcon
}>()
</script>
