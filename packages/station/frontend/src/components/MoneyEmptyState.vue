<script setup lang="ts">
import { HandCoins, Wallet } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import EmptyState from '@/components/ui/EmptyState.vue'
import { useStationStore } from '@/stores/station'

/** Shown by both money tabs until someone has actually bought credits. */
defineEmits<{ 'set-up': [] }>()

const station = useStationStore()
</script>

<template>
  <EmptyState
    :icon="HandCoins"
    title="No credits sold yet"
    :description="
      station.wallet
        ? 'Buyers purchase credits through SyftHub. What they spend at your spaces shows up here.'
        : 'Set up the shared wallet first — spaces bill against it, and what users spend shows up here.'
    "
  >
    <template v-if="!station.wallet" #actions>
      <Button size="sm" @click="$emit('set-up')">
        <Wallet class="mr-1.5 h-3.5 w-3.5" />
        Set up the wallet
      </Button>
    </template>
  </EmptyState>
</template>
