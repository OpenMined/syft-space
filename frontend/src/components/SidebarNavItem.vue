<script setup lang="ts">
import type { Component } from 'vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

interface Props {
  item: {
    label: string
    icon: Component
    active: boolean
    badgeValue: number | string | undefined
    badgeVariant?: 'default' | 'destructive' | 'secondary' | 'outline'
  }
  collapsed: boolean
}

defineProps<Props>()
defineEmits<{ (e: 'click'): void }>()
</script>

<template>
  <TooltipProvider v-if="collapsed" :delay-duration="0">
    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          :variant="item.active ? 'secondary' : 'ghost'"
          size="icon"
          class="w-full h-9 relative"
          :class="item.active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''"
          @click="$emit('click')"
        >
          <component :is="item.icon" class="h-5 w-5" />
          <Badge
            v-if="item.badgeValue"
            :variant="item.badgeVariant ?? 'secondary'"
            class="absolute -top-1 -right-1 h-5 min-w-[20px] flex items-center justify-center text-xs px-1"
          >
            {{ item.badgeValue }}
          </Badge>
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">
        {{ item.label }}
        <template v-if="item.badgeValue"> ({{ item.badgeValue }}) </template>
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
  <Button
    v-else
    :variant="item.active ? 'secondary' : 'ghost'"
    class="w-full justify-start h-9 px-3"
    :class="item.active ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''"
    @click="$emit('click')"
  >
    <component :is="item.icon" class="h-5 w-5 mr-3 shrink-0" />
    <span class="truncate flex-1 text-left">{{ item.label }}</span>
    <Badge
      v-if="item.badgeValue"
      :variant="item.badgeVariant ?? 'secondary'"
      class="ml-auto text-xs"
    >
      {{ item.badgeValue }}
    </Badge>
  </Button>
</template>
