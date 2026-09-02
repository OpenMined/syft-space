<script setup lang="ts">
import { Wallet } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { useStationStore } from '@/stores/station'

/** The saved wallet at a glance — provider, currency, hub connection. */

const station = useStationStore()

const PROVIDER_LABELS: Record<string, string> = { xendit: 'Xendit', stripe: 'Stripe' }
</script>

<template>
  <div
    v-if="station.wallet"
    class="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-2.5 text-sm"
  >
    <Wallet class="h-4 w-4 shrink-0 text-muted-foreground" />
    <span class="font-medium">
      {{ PROVIDER_LABELS[station.wallet.provider] ?? station.wallet.provider }}
    </span>
    <Badge variant="secondary">{{ station.wallet.currency }}</Badge>
    <Badge v-if="station.identity?.connected" variant="secondary">SyftHub connected</Badge>
  </div>
</template>
