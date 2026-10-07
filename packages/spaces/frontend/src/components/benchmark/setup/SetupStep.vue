<template>
  <section class="rounded-lg border border-border bg-card" :aria-labelledby="`${id}-title`">
    <div class="flex gap-4 p-5">
      <div
        class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 font-semibold text-primary"
        aria-hidden="true"
      >
        {{ step }}
      </div>
      <div class="flex min-w-0 flex-1 flex-col gap-3.5">
        <div class="space-y-0.5">
          <h2 :id="`${id}-title`" class="text-base font-semibold text-foreground">
            <span class="sr-only">Step {{ step }}: </span>{{ title }}
          </h2>
          <p class="text-sm text-muted-foreground">{{ description }}</p>
        </div>
        <slot />
      </div>
    </div>

    <details v-if="$slots.advanced" class="group/adv border-t border-border/70">
      <summary
        class="flex cursor-pointer list-none items-center gap-1.5 rounded-b-lg bg-muted/30 py-2.5 pr-5 pl-[68px] text-[13px] font-medium text-muted-foreground select-none hover:text-foreground [&::-webkit-details-marker]:hidden"
      >
        <ChevronRight class="size-4 transition-transform group-open/adv:rotate-90" />
        Advanced settings
      </summary>
      <div class="flex flex-col pr-5 pb-4 pl-[68px]">
        <slot name="advanced" />
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
/** One numbered step of the Benchmark tab, with its advanced settings folded away. */
import { ChevronRight } from 'lucide-vue-next'

defineProps<{ id: string; step: number; title: string; description: string }>()
</script>
