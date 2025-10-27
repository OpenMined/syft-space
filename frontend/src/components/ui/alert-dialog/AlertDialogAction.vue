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
})
</script>

<template>
  <DialogClose as-child>
    <Button
      :variant="props.variant"
      :class="cn(props.class)"
    >
      <slot />
    </Button>
  </DialogClose>
</template>