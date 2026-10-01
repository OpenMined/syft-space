<script setup lang="ts">
/**
 * A model's name, always in the same lemon-green chip.
 *
 * Whoever it is — the model under test, a grader, the one that wrote the
 * questions — a name is a name, and giving each role its own styling would
 * make the reader learn a colour code to read what the text already says. The
 * colour is light: a name carries no verdict, so it stays quieter than one.
 *
 * The house that serves it is dropped from the chip and kept on hover: the
 * vendor decides independence, not identity.
 */
import { Badge } from '@/components/ui/badge'
import { shortModel } from './labels'

defineProps<{ name: string }>()
</script>

<template>
  <Badge
    variant="secondary"
    class="font-normal bg-lime-300 text-lime-950 dark:bg-lime-400 dark:text-lime-950"
    :title="name"
  >
    {{ shortModel(name) }}
  </Badge>
</template>
