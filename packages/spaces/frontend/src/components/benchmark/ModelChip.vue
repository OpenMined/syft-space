<script setup lang="ts">
/**
 * A model's name, always in the same grey chip.
 *
 * Whoever it is — the model under test, a grader, the one that wrote the
 * questions — a name is a name, and giving each role its own styling would
 * make the reader learn a colour code to read what the text already says.
 *
 * The house that serves it is dropped from the chip and kept on hover: the
 * vendor decides independence, not identity, and repeated down a column it is
 * the same prefix over and over.
 */
import { Badge } from '@/components/ui/badge'
import { shortModel } from './labels'

defineProps<{ name: string }>()
</script>

<template>
  <Badge variant="secondary" class="font-normal" :title="name">{{ shortModel(name) }}</Badge>
</template>
