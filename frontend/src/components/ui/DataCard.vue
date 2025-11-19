<template>
  <Card
    class="transition-all hover:shadow-md cursor-pointer"
    :class="{ 'hover:shadow-lg': hoverable }"
    @click="$emit('click')"
  >
    <CardContent class="p-6">
      <div class="flex items-start justify-between">
        <div class="flex items-start gap-4 flex-1">
          <!-- Icon/Avatar slot -->
          <div v-if="$slots.icon" class="flex-shrink-0">
            <slot name="icon" />
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <!-- Header with title and badges -->
            <div class="flex items-start justify-between gap-3 mb-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-3 mb-2">
                  <h3 class="large truncate">
                    <slot name="title" />
                  </h3>
                  <slot name="badges" />
                </div>

                <!-- Description -->
                <div v-if="$slots.description" class="body-sm mb-4">
                  <slot name="description" />
                </div>

                <!-- Tags/Categories -->
                <div v-if="$slots.tags" class="flex flex-wrap gap-2">
                  <slot name="tags" />
                </div>
              </div>
            </div>

            <!-- Additional content slot -->
            <slot name="content" />
          </div>
        </div>

        <!-- Actions -->
        <div v-if="$slots.actions" class="flex items-center gap-2 ml-4">
          <slot name="actions" />
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { Card, CardContent } from '@/components/ui/card'

defineProps<{
  hoverable?: boolean
}>()

defineEmits<{
  click: []
}>()
</script>
