<script setup lang="ts">
import { Plus, ShieldCheck } from 'lucide-vue-next'
import SyftLogo from '@/assets/syftbox-logo.svg'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  /** Which view this header sits on — decided by the signed-in user's role. Omit when signed out. */
  variant?: 'member' | 'admin'
}>()

const emit = defineEmits<{ 'new-space': [] }>()
</script>

<template>
  <header
    class="flex h-12 w-full shrink-0 items-center gap-4 border-b border-border/40 bg-background px-4"
  >
    <div class="flex min-w-0 flex-1 items-center gap-2">
      <img :src="SyftLogo" alt="Syft Station" class="h-8 w-8 shrink-0" />
      <span class="truncate text-sm font-semibold tracking-tight">Syft Station</span>
      <Badge v-if="props.variant === 'admin'" variant="contrast" class="gap-1">
        <ShieldCheck class="h-3 w-3" />
        Admin
      </Badge>
    </div>

    <div class="flex items-center gap-2">
      <Button v-if="props.variant === 'admin'" size="sm" class="h-8" @click="emit('new-space')">
        <Plus class="mr-1 h-3.5 w-3.5" />
        New space
      </Button>
      <ThemeToggle />
    </div>
  </header>
</template>
