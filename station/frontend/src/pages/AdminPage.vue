<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowUpCircle,
  Check,
  ExternalLink,
  Inbox,
  KeyRound,
  LogOut,
  MoreVertical,
  Pause,
  Play,
  RotateCw,
  Save,
  ScrollText,
  Server,
  ServerOff,
  Settings,
  Tag,
  Trash2,
  TriangleAlert,
  User,
  Wallet,
  X,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import AppHeader from '@/components/AppHeader.vue'
import ApproveSpaceModal from '@/components/ApproveSpaceModal.vue'
import CreateSpaceDialog from '@/components/CreateSpaceDialog.vue'
import EarningsPanel from '@/components/EarningsPanel.vue'
import RejectRequestDialog from '@/components/RejectRequestDialog.vue'
import StationAnimation from '@/components/StationAnimation.vue'
import RequestStatusBadge from '@/components/RequestStatusBadge.vue'
import SetupStationDialog from '@/components/SetupStationDialog.vue'
import VersionSelect from '@/components/VersionSelect.vue'
import ViewLogsSheet from '@/components/ViewLogsSheet.vue'
import HealthBadge from '@/components/HealthBadge.vue'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import EmptyState from '@/components/ui/EmptyState.vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ApiError } from '@/api/client'
import type { Space, SpaceRequest } from '@/lib/types'
import { Label } from '@/components/ui/label'
import { useStationStore } from '@/stores/station'
import { useSessionStore } from '@/stores/session'

const station = useStationStore()
const session = useSessionStore()
const router = useRouter()

onMounted(() => {
  station.loadSetup().catch(() => toast.error('Could not load the station setup'))
  station.loadRequests().catch(() => toast.error('Could not load requests'))
  station.loadSpaces().catch(() => toast.error('Could not load spaces'))
})

// ---- Sidebar navigation (same shell as the syft-space sidebar) ----
type AdminSection = 'requests' | 'spaces' | 'earnings' | 'settings'
const activeSection = ref<AdminSection>('requests')

const mainNav = computed(() => [
  {
    id: 'requests' as AdminSection,
    label: 'Requests',
    icon: Inbox,
    badge: station.pendingCount > 0 ? station.pendingCount : undefined,
  },
])

const stationNav = computed(() => [
  {
    id: 'spaces' as AdminSection,
    label: 'Spaces',
    icon: Server,
    badge: station.spaces.length > 0 ? station.spaces.length : undefined,
  },
  { id: 'earnings' as AdminSection, label: 'Earnings', icon: Wallet, badge: undefined },
])

function signOut() {
  session.signOut()
  router.push({ name: 'signin' })
}

// ---- Requests tab ----
const approveTarget = ref<SpaceRequest | null>(null)
const approveOpen = ref(false)
const rejectTarget = ref<SpaceRequest | null>(null)
const rejectOpen = ref(false)
const createOpen = ref(false)

const openRequests = computed(() =>
  station.requests
    .filter((r) => r.status === 'pending' || r.status === 'provisioning' || r.status === 'failed')
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
)
const settledRequests = computed(() =>
  station.requests
    .filter((r) => r.status === 'active' || r.status === 'rejected' || r.status === 'deleted')
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
)

function openApprove(request: SpaceRequest) {
  approveTarget.value = request
  approveOpen.value = true
}

function openReject(request: SpaceRequest) {
  rejectTarget.value = request
  rejectOpen.value = true
}

// ---- Spaces tab ----
const deleteTarget = ref<Space | null>(null)
const deleteOpen = ref(false)
const logsTarget = ref<Space | null>(null)
const logsOpen = ref(false)

function openLogs(space: Space) {
  logsTarget.value = space
  logsOpen.value = true
}
const deleting = ref(false)

function openDelete(space: Space) {
  deleteTarget.value = space
  deleteOpen.value = true
}

/** A FAILED request's leftover resources are torn down via the same dialog. */
function openDeleteFailed(request: SpaceRequest) {
  const space = request.spaceId ? station.spaceById(request.spaceId) : undefined
  if (space) openDelete(space)
  else toast.error('Could not find the space for this request')
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  const name = deleteTarget.value.name
  deleting.value = true
  try {
    await station.deleteSpace(deleteTarget.value.id)
    toast('Space deleted, along with its data', { description: name })
    deleteOpen.value = false
  } catch {
    toast.error('Deleting the space failed')
  } finally {
    deleting.value = false
  }
}

const outdatedCount = computed(
  () => station.spaces.filter((s) => s.version !== station.supportedVersion).length,
)

function updateAll() {
  toast('Update all is not available yet', {
    description: `${outdatedCount.value} space(s) behind ${station.supportedVersion}`,
  })
}

// ---- Settings ----
const versionInput = ref('')
const savingVersion = ref(false)

async function saveVersion() {
  const version = versionInput.value.trim()
  if (!version || version === station.supportedVersion) return
  savingVersion.value = true
  try {
    await station.setSupportedVersion(version)
    toast.success(`Supported version set to ${version}`, {
      description: 'Use "Update all" on Spaces to roll it out.',
    })
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Saving the version failed')
  } finally {
    savingVersion.value = false
  }
}

async function regenerateKey(space: Space) {
  try {
    await station.regenerateApiKey(space.id)
    toast('New API key issued', {
      description: `${space.ownerEmail} can claim it from their dashboard.`,
    })
  } catch {
    toast.error('Regenerating the key failed')
  }
}

function restart(space: Space) {
  toast('Restart is not available yet', { description: space.name })
}

async function pause(space: Space) {
  try {
    await station.pauseSpace(space.id)
    toast('Space paused — data retained, no compute used', { description: space.name })
  } catch {
    toast.error('Pausing the space failed')
  }
}

async function start(space: Space) {
  toast('Starting space', { description: space.name })
  await station.startSpace(space.id).catch(() => toast.error('Starting the space failed'))
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-background">
    <AppHeader
      variant="admin"
      @new-space="createOpen = true"
      @go="(section) => (activeSection = section)"
    />
    <div class="flex min-h-0 flex-1 overflow-hidden">
      <!-- Sidebar -->
      <aside class="flex w-60 shrink-0 flex-col border-r border-border/40 bg-background">
        <nav class="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          <Button
            v-for="item in mainNav"
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

          <div class="pt-4">
            <p
              class="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Station
            </p>
            <div class="space-y-0.5">
              <Button
                v-for="item in stationNav"
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
            </div>
          </div>
        </nav>

        <!-- User card + Settings (same footer as the syft-space sidebar) -->
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
                  <Button
                    :variant="activeSection === 'settings' ? 'secondary' : 'ghost'"
                    size="icon"
                    class="h-8 w-8 shrink-0"
                    :class="
                      activeSection === 'settings'
                        ? 'text-primary bg-primary/8 hover:bg-primary/12'
                        : ''
                    "
                    @click="activeSection = 'settings'"
                  >
                    <Settings class="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">Settings</TooltipContent>
              </Tooltip>
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
        <div class="mx-auto w-full max-w-5xl px-6 py-8">
          <!-- ==================== Requests ==================== -->
          <div v-if="activeSection === 'requests'" class="space-y-8">
            <section class="space-y-3">
              <h2 class="text-sm font-medium text-muted-foreground">Needs attention</h2>

              <EmptyState
                v-if="openRequests.length === 0"
                :icon="Inbox"
                title="Queue is clear"
                description="New space requests will appear here for review."
              />

              <Card v-for="request in openRequests" :key="request.id">
                <CardContent class="flex flex-wrap items-center justify-between gap-3">
                  <div class="min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-medium">{{ request.spaceName }}</span>
                      <RequestStatusBadge :status="request.status" />
                    </div>
                    <div class="mt-0.5 text-xs text-muted-foreground">
                      <template v-if="request.origin === 'admin'">Created by admin for</template>
                      {{ request.requesterEmail }} · {{ formatDate(request.createdAt) }}
                    </div>
                    <p v-if="request.purpose" class="mt-1.5 text-sm text-muted-foreground">
                      {{ request.purpose }}
                    </p>
                    <p
                      v-if="request.status === 'failed' && request.failureError"
                      class="mt-1.5 flex items-center gap-1.5 text-xs text-destructive"
                    >
                      <TriangleAlert class="h-3.5 w-3.5 shrink-0" />
                      {{ request.failureError }}
                    </p>
                  </div>

                  <div class="flex shrink-0 items-center gap-2">
                    <template v-if="request.status === 'pending'">
                      <Button size="sm" variant="outline" @click="openReject(request)">
                        <X class="mr-1 h-3.5 w-3.5" />
                        Reject
                      </Button>
                      <Button size="sm" @click="openApprove(request)">
                        <Check class="mr-1 h-3.5 w-3.5" />
                        Approve
                      </Button>
                    </template>
                    <template v-else-if="request.status === 'failed'">
                      <Button size="sm" variant="outline" @click="openDeleteFailed(request)">
                        <Trash2 class="mr-1 h-3.5 w-3.5" />
                        Delete
                      </Button>
                      <Button size="sm" @click="openApprove(request)">
                        <RotateCw class="mr-1 h-3.5 w-3.5" />
                        Retry
                      </Button>
                    </template>
                    <StationAnimation
                      v-else-if="request.status === 'provisioning'"
                      mini
                      class="h-10 w-10 shrink-0"
                    />
                  </div>
                </CardContent>
              </Card>
            </section>

            <section v-if="settledRequests.length > 0" class="space-y-3">
              <h2 class="text-sm font-medium text-muted-foreground">History</h2>
              <Card>
                <CardContent class="divide-y p-0">
                  <div
                    v-for="request in settledRequests"
                    :key="request.id"
                    class="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
                  >
                    <div>
                      <span class="text-sm font-medium">{{ request.spaceName }}</span>
                      <span class="ml-2 text-xs text-muted-foreground">
                        {{ request.requesterEmail }}
                      </span>
                    </div>
                    <RequestStatusBadge :status="request.status" />
                  </div>
                </CardContent>
              </Card>
            </section>
          </div>

          <!-- ==================== Spaces ==================== -->
          <div v-else-if="activeSection === 'spaces'" class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Tag class="h-3.5 w-3.5" />
                Supported Syft Space version:
                <span class="font-mono font-medium text-foreground">{{
                  station.supportedVersion
                }}</span>
              </p>
              <Button v-if="outdatedCount > 0" size="sm" variant="outline" @click="updateAll">
                <ArrowUpCircle class="mr-1.5 h-3.5 w-3.5" />
                Update all ({{ outdatedCount }} outdated)
              </Button>
            </div>

            <EmptyState
              v-if="station.spaces.length === 0"
              :icon="ServerOff"
              title="No spaces yet"
              description="Spaces appear here once you approve a request."
            />

            <Card v-for="space in station.spaces" :key="space.id">
              <CardContent class="flex flex-wrap items-center justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ space.name }}</span>
                    <HealthBadge :health="space.health" />
                  </div>
                  <a
                    :href="space.url"
                    target="_blank"
                    rel="noopener"
                    class="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:underline"
                  >
                    {{ space.url.replace('https://', '') }}
                    <ExternalLink class="h-3 w-3" />
                  </a>
                  <div
                    class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
                  >
                    <span>{{ space.ownerEmail }}</span>
                    <span>since {{ formatDate(space.createdAt) }}</span>
                    <span class="font-mono">{{ space.version }}</span>
                    <Badge
                      v-if="space.version !== station.supportedVersion"
                      variant="outline"
                      class="gap-1 border-warning/50 bg-warning/10 px-1.5 py-0 text-[11px] font-normal"
                    >
                      <ArrowUpCircle class="h-3 w-3" />
                      update available
                    </Badge>
                    <Badge
                      v-if="station.wallet && !space.walletSeeded"
                      variant="outline"
                      class="gap-1 border-warning/50 bg-warning/10 px-1.5 py-0 text-[11px] font-normal"
                    >
                      <Wallet class="h-3 w-3" />
                      wallet applies on restart
                    </Badge>
                  </div>
                </div>

                <div class="flex shrink-0 items-center gap-2">
                  <Button
                    v-if="space.health === 'paused' || space.health === 'starting'"
                    size="sm"
                    :disabled="space.health === 'starting'"
                    @click="start(space)"
                  >
                    <Play class="mr-1 h-3.5 w-3.5" />
                    {{ space.health === 'starting' ? 'Starting…' : 'Start' }}
                  </Button>
                  <Button
                    v-else
                    size="sm"
                    variant="outline"
                    :disabled="space.health === 'restarting'"
                    @click="pause(space)"
                  >
                    <Pause class="mr-1 h-3.5 w-3.5" />
                    Pause
                  </Button>

                  <DropdownMenu>
                    <DropdownMenuTrigger as-child>
                      <Button size="sm" variant="ghost" class="px-2">
                        <MoreVertical class="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        :disabled="
                          space.health === 'paused' ||
                          space.health === 'restarting' ||
                          space.health === 'starting'
                        "
                        @click="restart(space)"
                      >
                        <RotateCw class="mr-2 h-3.5 w-3.5" />
                        Restart
                      </DropdownMenuItem>
                      <DropdownMenuItem @click="openLogs(space)">
                        <ScrollText class="mr-2 h-3.5 w-3.5" />
                        View logs
                      </DropdownMenuItem>
                      <DropdownMenuItem @click="regenerateKey(space)">
                        <KeyRound class="mr-2 h-3.5 w-3.5" />
                        Regenerate API key
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem variant="destructive" @click="openDelete(space)">
                        <Trash2 class="mr-2 h-3.5 w-3.5" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardContent>
            </Card>
          </div>

          <!-- ==================== Earnings ==================== -->
          <EarningsPanel v-else-if="activeSection === 'earnings'" />

          <!-- ==================== Settings ==================== -->
          <div v-else class="max-w-xl space-y-6">
            <Card>
              <CardContent class="space-y-3">
                <div>
                  <p class="flex items-center gap-1.5 text-sm font-medium">
                    <Tag class="h-3.5 w-3.5" />
                    Supported Syft Space version
                  </p>
                  <p class="mt-0.5 text-xs text-muted-foreground">
                    New spaces deploy this version. Existing spaces are updated with "Update all" on
                    the Spaces page — downgrades are not supported.
                  </p>
                </div>
                <div class="flex items-end gap-2">
                  <div class="flex-1 space-y-1.5">
                    <Label>Version</Label>
                    <VersionSelect v-model="versionInput" />
                  </div>
                  <Button
                    :disabled="
                      savingVersion ||
                      !versionInput.trim() ||
                      versionInput === station.supportedVersion
                    "
                    @click="saveVersion"
                  >
                    <Save class="mr-1.5 h-3.5 w-3.5" />
                    Save
                  </Button>
                </div>
                <p class="text-xs text-muted-foreground">
                  Currently deploying:
                  <span class="font-mono">{{ station.supportedVersion || '—' }}</span>
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent class="space-y-3">
                <p class="text-sm font-medium">Station</p>
                <dl class="space-y-2 text-sm">
                  <div class="flex justify-between gap-4">
                    <dt class="text-muted-foreground">Space domain</dt>
                    <dd class="font-mono text-xs">*.{{ station.domain }}</dd>
                  </div>
                </dl>
                <div class="rounded-md border bg-muted/40 px-3 py-2.5">
                  <p class="mb-1.5 text-xs font-medium text-muted-foreground">Every space gets</p>
                  <ul class="space-y-1">
                    <li
                      v-for="item in station.spaceIncludes"
                      :key="item"
                      class="flex items-center gap-1.5 text-xs text-muted-foreground"
                    >
                      <Check class="h-3 w-3 shrink-0 text-success" />
                      {{ item }}
                    </li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  </div>

  <!-- First-run setup — shown until the admin sets the station domain -->
  <SetupStationDialog :open="station.setupLoaded && !station.onboarded" />

  <ApproveSpaceModal v-model:open="approveOpen" :request="approveTarget" />
  <ViewLogsSheet v-model:open="logsOpen" :space="logsTarget" />
  <RejectRequestDialog v-model:open="rejectOpen" :request="rejectTarget" />
  <CreateSpaceDialog v-model:open="createOpen" />

  <!-- Delete confirm — teardown removes the data too -->
  <Dialog v-model:open="deleteOpen">
    <DialogContent v-if="deleteTarget">
      <DialogHeader>
        <DialogTitle>Delete “{{ deleteTarget.name }}”?</DialogTitle>
        <DialogDescription>
          The space stops running and its URL is released.
          <span class="font-medium text-destructive">
            All of its data — files and search index — is deleted permanently.
          </span>
          This cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <DialogFooter>
        <Button variant="outline" @click="deleteOpen = false">Cancel</Button>
        <Button variant="destructive" :disabled="deleting" @click="confirmDelete()">
          Delete space and data
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
