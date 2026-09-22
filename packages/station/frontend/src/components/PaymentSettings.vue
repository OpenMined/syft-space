<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Copy, ExternalLink, Pencil, Wallet } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import ConfigureWalletDialog from '@/components/ConfigureWalletDialog.vue'
import HelpTip from '@/components/HelpTip.vue'
import SpacesOnWalletCard from '@/components/SpacesOnWalletCard.vue'
import SyftHubIdentityCard from '@/components/SyftHubIdentityCard.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import EmptyState from '@/components/ui/EmptyState.vue'
import { Skeleton } from '@/components/ui/skeleton'
import { DOCS } from '@/lib/docs'
import { useStationStore } from '@/stores/station'

const station = useStationStore()
const walletOpen = ref(false)

onMounted(() => {
  // Spaces come along for the attachment table: which spaces are on the
  // wallet is part of configuring the rail.
  Promise.all([station.loadWallet(), station.loadSpaces()]).catch(() =>
    toast.error('Could not load the payment settings'),
  )
})

/** Where the payment provider must deliver its events. */
const webhookUrl = computed(
  () => `${window.location.origin}/api/v1/credits/webhooks/${station.wallet?.provider ?? 'xendit'}`,
)

const isStripe = computed(() => station.wallet?.provider === 'stripe')

/** The provider's dashboard page where the webhook endpoint is set up. */
const webhookDashboard = computed(() =>
  isStripe.value
    ? 'the Stripe Dashboard under Developers → Webhooks'
    : 'the Xendit dashboard under Settings → Developers → Webhooks',
)

function copyWebhookUrl() {
  navigator.clipboard.writeText(webhookUrl.value)
  toast('Webhook URL copied', { description: `Paste it in ${webhookDashboard.value}.` })
}
</script>

<template>
  <div class="space-y-8">
    <div v-if="!station.walletLoaded" class="space-y-3">
      <Skeleton class="h-5 w-24" />
      <Skeleton class="h-32 w-full" />
    </div>

    <EmptyState
      v-else-if="!station.wallet"
      :icon="Wallet"
      title="No shared wallet"
      description="Add one payment account to sell credits that work at every space. You collect the money and pay members for what users spend."
    >
      <template #actions>
        <Button size="sm" @click="walletOpen = true">
          <Wallet class="mr-1.5 h-3.5 w-3.5" />
          Add shared wallet
        </Button>
        <Button as="a" size="sm" variant="outline" :href="DOCS.creditsAndPayouts" target="_blank">
          How credits work
          <ExternalLink class="ml-1.5 h-3.5 w-3.5" />
        </Button>
      </template>
    </EmptyState>

    <template v-else>
      <section class="space-y-2">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <h2 class="text-sm font-medium">Wallet</h2>
          <a
            :href="DOCS.creditsAndPayouts"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            How credits work
            <ExternalLink class="h-3 w-3" />
          </a>
        </div>

        <dl class="divide-y rounded-lg border bg-card text-sm">
          <div class="flex flex-wrap items-center gap-3 px-4 py-3">
            <dt class="w-32 shrink-0 text-muted-foreground">Provider</dt>
            <dd class="flex min-w-0 flex-1 items-center gap-2">
              <span class="font-medium capitalize">{{ station.wallet.provider }}</span>
              <Badge variant="secondary">{{ station.wallet.currency }}</Badge>
            </dd>
            <Button size="sm" variant="outline" @click="walletOpen = true">
              <Pencil class="mr-1.5 h-3.5 w-3.5" />
              Replace
            </Button>
          </div>

          <div class="flex flex-wrap items-center gap-3 px-4 py-3">
            <dt class="flex w-32 shrink-0 items-center gap-1.5 text-muted-foreground">
              Webhook
              <HelpTip>
                Payment events are delivered here. Set it in {{ webhookDashboard }}, with the
                {{ isStripe ? 'signing secret' : 'callback token' }} from the same page. The gateway
                key stays at the station.
              </HelpTip>
            </dt>
            <dd class="min-w-0 flex-1 truncate font-mono text-xs">{{ webhookUrl }}</dd>
            <Button size="sm" variant="ghost" @click="copyWebhookUrl">
              <Copy class="h-3.5 w-3.5" />
            </Button>
          </div>

          <div class="px-4 py-3">
            <SyftHubIdentityCard />
          </div>
        </dl>
      </section>

      <SpacesOnWalletCard />
    </template>
  </div>

  <ConfigureWalletDialog v-model:open="walletOpen" />
</template>
