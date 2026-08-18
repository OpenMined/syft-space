<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { HandCoins, Inbox, LogOut, Plus, User } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import AppHeader from '@/components/AppHeader.vue'
import MyRequests from '@/components/MyRequests.vue'
import RequestForm from '@/components/RequestForm.vue'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'
import { useSessionStore } from '@/stores/session'

const station = useStationStore()
const session = useSessionStore()
const router = useRouter()

// Setup (for the domain in URLs) + this member's requests, spaces and earnings
onMounted(async () => {
  station.loadSetup().catch(() => {})
  station.loadWallet().catch(() => {})
  station.loadMemberEarnings().catch(() => {})
  await Promise.all([station.loadRequests(), station.loadSpaces()]).catch(() => {})
  // Land returning members on their requests once real data is in
  if (myRequestCount.value > 0) activeSection.value = 'requests'
})

// ---- Sidebar navigation (same shell as the syft-space sidebar) ----
type MemberSection = 'requests' | 'new'

// Total requests the member has made. Every request is represented in the view
// — active ones as cards, settled ones in History — so the raw count matches.
const myRequestCount = computed(() =>
  session.profile ? station.requestsFor(session.profile.email).length : 0,
)

// Land newcomers on the request form, returning members on their spaces
const activeSection = ref<MemberSection>(myRequestCount.value > 0 ? 'requests' : 'new')

// The admin's decisions land from another session, so coming back to "My
// requests" refetches, and a background poll moves pending → active (and the
// space list) without a manual reload.
watch(activeSection, (section) => {
  if (section === 'requests') {
    station.loadRequests().catch(() => {})
    station.loadSpaces().catch(() => {})
  }
})

const REFRESH_INTERVAL_MS = 30_000
const refreshTimer = setInterval(() => {
  if (document.hidden) return
  station.loadRequests().catch(() => {})
  if (activeSection.value === 'requests') station.loadSpaces().catch(() => {})
}, REFRESH_INTERVAL_MS)
onUnmounted(() => clearInterval(refreshTimer))

const navItems = computed(() => [
  {
    id: 'requests' as MemberSection,
    label: 'My requests',
    icon: Inbox,
    badge: myRequestCount.value > 0 ? myRequestCount.value : undefined,
  },
  { id: 'new' as MemberSection, label: 'Request a space', icon: Plus, badge: undefined },
])

function signOut() {
  session.signOut()
  router.push({ name: 'signin' })
}

// ---- One space per account (SyftHub limit) ----
// While a request/space holds the slot, the form is replaced by an
// explainer that names the blocker and the way out.
// The slot is held by an in-flight create request or a live space; either
// way the request form is replaced by an explainer naming the blocker.
const myInflightCreate = computed(() =>
  session.profile ? station.inflightCreatesFor(session.profile.email)[0] : undefined,
)
const myLiveSpace = computed(() =>
  session.profile
    ? station.spaces.find((s) => s.ownerEmail === session.profile!.email)
    : undefined,
)
const slotHeld = computed(() => !!(myInflightCreate.value || myLiveSpace.value))
const slotName = computed(
  () => myInflightCreate.value?.spaceName ?? myLiveSpace.value?.name ?? '',
)
const slotExplanation = computed(() => {
  if (myLiveSpace.value)
    return 'is already running. Request its deletion from "My requests" to start over.'
  const byStatus: Record<string, string> = {
    pending: 'is awaiting review. Withdraw it if you want to request a different space.',
    provisioning: 'is being set up right now.',
    failed: 'failed to provision and is with the station admin to retry or delete.',
  }
  return byStatus[myInflightCreate.value?.status ?? ''] ?? ''
})

const withdrawing = ref(false)

async function withdrawLiveRequest() {
  const request = myInflightCreate.value
  if (!request) return
  withdrawing.value = true
  try {
    await station.withdrawRequest(request.id)
    toast('Request withdrawn', { description: request.spaceName })
  } catch {
    toast.error('Withdrawing the request failed')
  } finally {
    withdrawing.value = false
  }
}

// ---- What this member's spaces have earned but not yet been paid ----
// The headline is payable (earned − already paid out); earned is context.
const myEarnings = computed(() => station.memberEarnings?.spaces ?? [])
const totalOwed = computed(() => station.memberEarnings?.total_payable ?? 0)
const totalEarned = computed(() => station.memberEarnings?.total_earned ?? 0)
const currency = computed(() => station.wallet?.currency ?? 'USD')
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-background">
    <AppHeader variant="member" />
    <div class="flex min-h-0 flex-1 overflow-hidden">
      <!-- Sidebar -->
      <aside class="flex w-60 shrink-0 flex-col border-r border-border/40 bg-background">
        <nav class="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          <Button
            v-for="item in navItems"
            :key="item.id"
            :variant="activeSection === item.id ? 'secondary' : 'ghost'"
            class="h-9 w-full justify-start px-3"
            :class="
              activeSection === item.id ? 'text-primary bg-primary/8 hover:bg-primary/12' : ''
            "
            @click="activeSection = item.id"
          >
            <component :is="item.icon" class="mr-3 h-5 w-5 shrink-0" />
            <span class="flex-1 truncate text-left">{{ item.label }}</span>
            <Badge v-if="item.badge" variant="secondary" class="ml-auto text-xs">
              {{ item.badge }}
            </Badge>
          </Button>
        </nav>

        <!-- User card (same footer as the syft-space sidebar) -->
        <div class="mt-auto border-t border-border px-2 py-3">
          <div class="flex items-center gap-2 rounded-lg p-2">
            <Avatar class="h-8 w-8 shrink-0">
              <AvatarFallback class="bg-muted text-xs text-muted-foreground">
                <User class="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
            <p class="min-w-0 flex-1 truncate text-sm font-medium">
              {{ session.profile?.email }}
            </p>
            <TooltipProvider :delay-duration="0">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button variant="ghost" size="icon" class="h-8 w-8 shrink-0" @click="signOut">
                    <LogOut class="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">Sign out</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </aside>

      <main class="min-w-0 flex-1 overflow-y-auto">
        <div class="mx-auto w-full max-w-3xl px-6 py-8">
          <!-- Earnings awaiting payout across this member's spaces -->
          <Card
            v-if="activeSection === 'requests' && station.wallet && myEarnings.length > 0"
            class="mb-6"
          >
            <CardContent>
              <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
                <HandCoins class="h-3.5 w-3.5" />
                To be paid out to you
              </p>
              <p class="mt-1 text-2xl font-semibold tracking-tight">
                {{ formatMoney(totalOwed, currency) }}
              </p>
              <p class="mt-0.5 text-xs text-muted-foreground">
                {{ formatMoney(totalEarned, currency) }} earned across
                {{ myEarnings.length }} space{{ myEarnings.length === 1 ? '' : 's' }} — the station
                admin pays out manually.
              </p>
            </CardContent>
          </Card>

          <MyRequests v-if="activeSection === 'requests'" />
          <div v-else class="max-w-xl">
            <Card v-if="slotHeld">
              <CardHeader>
                <CardTitle class="text-base">One space per account</CardTitle>
                <CardDescription>
                  Your {{ myLiveSpace ? 'space' : 'request' }} '{{ slotName }}'
                  {{ slotExplanation }}
                </CardDescription>
              </CardHeader>
              <CardContent class="flex gap-2">
                <Button variant="outline" size="sm" @click="activeSection = 'requests'">
                  View my requests
                </Button>
                <Button
                  v-if="myInflightCreate?.status === 'pending'"
                  variant="destructive"
                  size="sm"
                  :disabled="withdrawing"
                  @click="withdrawLiveRequest"
                >
                  Withdraw request
                </Button>
              </CardContent>
            </Card>
            <RequestForm v-else @submitted="activeSection = 'requests'" />
          </div>
        </div>
      </main>
    </div>
  </div>
</template>
