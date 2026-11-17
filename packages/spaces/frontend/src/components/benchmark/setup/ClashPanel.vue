<template>
  <div
    role="alert"
    class="mb-3 flex flex-col gap-2 rounded-lg border border-amber-500 bg-amber-50 px-3.5 py-3 dark:bg-amber-500/10"
    data-testid="clash-panel"
  >
    <div class="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-300">
      <TriangleAlert class="size-4" />
      {{
        blocked
          ? 'Can’t save or run yet: a judge is from the same company as a model being tested'
          : 'A judge is from the same company as a model being tested'
      }}
    </div>
    <div
      v-for="clash in clashes"
      :key="`${clash.judge}-${clash.model}`"
      class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2"
    >
      <span class="text-sm">
        Judge {{ clash.judge + 1 }} ({{ nameOf(clash.judgeModel) }}) and {{ nameOf(clash.model) }},
        a model being tested, are both from {{ companyName(clash.company) }}.
      </span>
      <Button variant="outline" size="sm" @click="emit('removeModel', clash.model)">
        Remove {{ nameOf(clash.model) }} from the test
      </Button>
    </div>
    <span class="text-xs text-amber-800 dark:text-amber-300">
      {{
        blocked
          ? 'Pick a different judge in step 5, or remove the model. You can change this rule in step 5’s advanced settings.'
          : 'If you run anyway, that judge’s grades for that model will be flagged in the results.'
      }}
    </span>
  </div>
</template>

<script setup lang="ts">
/** Judges that share a company with a tested model, and a way to drop that model. */
import { TriangleAlert } from 'lucide-vue-next'

import { Button } from '@/components/ui/button'
import { companyName, type Clash } from './models'

defineProps<{
  clashes: Clash[]
  /** The same-company rule refuses to save or run. */
  blocked: boolean
  nameOf: (id: string) => string
}>()

const emit = defineEmits<{ removeModel: [string] }>()
</script>
