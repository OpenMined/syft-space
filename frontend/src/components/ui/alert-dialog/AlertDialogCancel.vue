<script setup lang="ts">
import { DialogClose, type DialogCloseProps } from 'radix-vue'
import { Button, type ButtonProps } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Props extends DialogCloseProps {
  variant?: ButtonProps['variant']
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  class: '',
  variant: 'outline',
})
</script>

<template>
  <DialogClose as-child>
    <Button
      :variant="props.variant"
      :class="cn('mt-2 sm:mt-0', props.class)"
    >
      <slot />
    </Button>
  </DialogClose>
</template>