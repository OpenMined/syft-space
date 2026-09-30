<script setup lang="ts">
/** Where the published card can be seen — an eye, and the list behind it. */
import { Eye } from 'lucide-vue-next'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { RunMarketplace } from './runs'

defineProps<{ marketplaces: RunMarketplace[] }>()
</script>

<template>
  <Popover>
    <PopoverTrigger as-child>
      <button
        type="button"
        class="text-muted-foreground hover:text-foreground shrink-0"
        aria-label="Where this card is visible"
        @click.stop
      >
        <Eye class="h-4 w-4" />
      </button>
    </PopoverTrigger>
    <PopoverContent class="w-72 text-xs" align="end" @click.stop>
      <p class="font-medium text-foreground mb-2">Visible at</p>
      <ul class="space-y-1.5">
        <li v-for="place in marketplaces" :key="place.id">
          <a
            :href="place.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary hover:underline break-all"
          >
            {{ place.name }}
          </a>
        </li>
      </ul>
    </PopoverContent>
  </Popover>
</template>
