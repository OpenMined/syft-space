<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Inbox,
  Globe,
  Slack,
  Phone,
  Send,
  X,
  Search,
  ChevronDown,
  Sparkles,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import SortButton from '@/components/SortButton.vue'
import TablePagination from '@/components/TablePagination.vue'
import { useTableControls } from '@/composables/useTableControls'
import { useTriageStore, type TriageItem } from '@/stores/triage'
import { getPersonById } from '@/stores/mockRelationships'
import { PLATFORMS, getPlatformLabel, type Platform } from '@/stores/mockApis'
import { toast } from 'vue-sonner'

const router = useRouter()
const triage = useTriageStore()

const icons: Record<Platform, typeof Globe> = {
  syfthub: Globe,
  slack: Slack,
  whatsapp: Phone,
}

const personFor = (personId: string) => getPersonById(personId)

type Tab = 'all' | Platform
const activeTab = ref<Tab>('all')

const countFor = (platform: Platform) =>
  triage.pendingTriage.filter((i) => i.platform === platform).length

const tabs = computed(() => [
  { id: 'all' as Tab, label: 'All', count: triage.pendingTriage.length },
  ...PLATFORMS.map((p) => ({ id: p.id as Tab, label: p.label, count: countFor(p.id) })),
])

const scoped = computed<TriageItem[]>(() =>
  activeTab.value === 'all'
    ? triage.pendingTriage
    : triage.pendingTriage.filter((i) => i.platform === activeTab.value),
)

const controls = useTableControls(scoped, {
  searchText: (i) =>
    `${personFor(i.personId)?.name ?? ''} ${i.incomingMessage} ${i.suggestedAction}`,
  sorters: {
    person: (i) => personFor(i.personId)?.name.toLowerCase() ?? '',
    action: (i) => i.suggestedAction.toLowerCase(),
    time: (i) => i.timestamp.getTime(),
  },
  initialSort: { key: 'time', dir: 'desc' },
  pageSize: 25,
})

watch(activeTab, () => {
  controls.page.value = 1
})

const colspan = computed(() => (activeTab.value === 'all' ? 7 : 6))

// --- Expand-to-act --------------------------------------------------------
const expandedId = ref<string | null>(null)
const toggleExpand = (id: string) => {
  expandedId.value = expandedId.value === id ? null : id
}

// --- Bulk selection -------------------------------------------------------
const selected = ref<Set<string>>(new Set())
const isSelected = (id: string) => selected.value.has(id)
const toggleSelect = (id: string) => {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}
const pageIds = computed(() => controls.paged.value.map((i) => i.id))
const allPageSelected = computed(
  () => pageIds.value.length > 0 && pageIds.value.every((id) => selected.value.has(id)),
)
const somePageSelected = computed(() => pageIds.value.some((id) => selected.value.has(id)))
const headerState = computed<boolean | 'indeterminate'>(() =>
  allPageSelected.value ? true : somePageSelected.value ? 'indeterminate' : false,
)
const toggleSelectAll = () => {
  const next = new Set(selected.value)
  if (allPageSelected.value) pageIds.value.forEach((id) => next.delete(id))
  else pageIds.value.forEach((id) => next.add(id))
  selected.value = next
}
const clearSelection = () => {
  selected.value = new Set()
}
const selectedCount = computed(() => selected.value.size)

const forget = (id: string) => {
  if (selected.value.has(id)) {
    const next = new Set(selected.value)
    next.delete(id)
    selected.value = next
  }
  if (expandedId.value === id) expandedId.value = null
}

const onSend = (id: string) => {
  triage.sendTriage(id)
  forget(id)
  toast.success('Reply sent')
}
const onDismiss = (id: string) => {
  triage.dismissTriage(id)
  forget(id)
  toast.success('Dismissed')
}

const bulkSend = () => {
  const ids = [...selected.value]
  ids.forEach((id) => triage.sendTriage(id))
  expandedId.value = null
  clearSelection()
  toast.success(`Sent ${ids.length} ${ids.length === 1 ? 'reply' : 'replies'}`)
}
const bulkDismiss = () => {
  const ids = [...selected.value]
  ids.forEach((id) => triage.dismissTriage(id))
  expandedId.value = null
  clearSelection()
  toast.success(`Dismissed ${ids.length}`)
}

const formatTime = (date: Date) =>
  date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Triage</h1>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Drafted replies awaiting your approval — only for people in manual mode. Select a row to
        review the draft and reasoning, or act on many at once.
      </p>
    </div>

    <!-- Empty -->
    <div v-if="triage.pendingTriage.length === 0" class="text-center py-20">
      <Inbox class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">Inbox zero</h3>
      <p class="body-sm text-muted-foreground">No replies are waiting for approval.</p>
    </div>

    <template v-else>
      <!-- Platform tabs -->
      <Tabs v-model="activeTab" class="mb-5">
        <TabsList>
          <TabsTrigger v-for="t in tabs" :key="t.id" :value="t.id" class="gap-1.5">
            <component v-if="t.id !== 'all'" :is="icons[t.id as Platform]" class="h-3.5 w-3.5" />
            {{ t.label }}
            <span class="text-xs text-muted-foreground tabular-nums">{{ t.count }}</span>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Toolbar -->
      <div class="flex flex-col gap-3 mb-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="relative w-full sm:max-w-xs">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            v-model="controls.search.value"
            placeholder="Search person or message…"
            class="pl-9 h-9"
          />
        </div>

        <!-- Bulk action bar -->
        <div v-if="selectedCount > 0" class="flex items-center gap-2 shrink-0">
          <span class="text-xs text-muted-foreground">{{ selectedCount }} selected</span>
          <Button variant="ghost" size="sm" @click="bulkDismiss">
            <X class="h-4 w-4 mr-1.5" />
            Dismiss
          </Button>
          <Button size="sm" @click="bulkSend">
            <Send class="h-4 w-4 mr-1.5" />
            Send all
          </Button>
          <Button variant="ghost" size="sm" class="text-muted-foreground" @click="clearSelection">
            Clear
          </Button>
        </div>
      </div>

      <!-- Table -->
      <div class="rounded-xl border border-border bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow class="hover:bg-transparent bg-muted/40">
              <TableHead class="w-10">
                <Checkbox
                  :model-value="headerState"
                  aria-label="Select all on page"
                  @update:model-value="toggleSelectAll"
                />
              </TableHead>
              <TableHead>
                <SortButton
                  label="Person"
                  column-key="person"
                  :active-key="controls.sortKey.value"
                  :dir="controls.sortDir.value"
                  @toggle="controls.toggleSort"
                />
              </TableHead>
              <TableHead v-if="activeTab === 'all'">Platform</TableHead>
              <TableHead class="hidden md:table-cell">Incoming</TableHead>
              <TableHead>
                <SortButton
                  label="Action"
                  column-key="action"
                  :active-key="controls.sortKey.value"
                  :dir="controls.sortDir.value"
                  @toggle="controls.toggleSort"
                />
              </TableHead>
              <TableHead class="text-right">
                <span class="inline-flex">
                  <SortButton
                    label="Received"
                    column-key="time"
                    :active-key="controls.sortKey.value"
                    :dir="controls.sortDir.value"
                    @toggle="controls.toggleSort"
                  />
                </span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <template v-for="item in controls.paged.value" :key="item.id">
              <TableRow
                class="cursor-pointer"
                :data-state="isSelected(item.id) ? 'selected' : undefined"
                @click="toggleExpand(item.id)"
              >
                <TableCell class="w-10" @click.stop>
                  <Checkbox
                    :model-value="isSelected(item.id)"
                    :aria-label="`Select ${personFor(item.personId)?.name}`"
                    @update:model-value="toggleSelect(item.id)"
                  />
                </TableCell>
                <TableCell>
                  <div class="flex items-center gap-3">
                    <Avatar class="h-8 w-8 shrink-0">
                      <AvatarFallback class="bg-muted text-muted-foreground text-xs">
                        {{ personFor(item.personId)?.avatarInitials }}
                      </AvatarFallback>
                    </Avatar>
                    <div class="min-w-0">
                      <p class="font-medium text-foreground truncate">
                        {{ personFor(item.personId)?.name }}
                      </p>
                      <p class="text-xs text-muted-foreground truncate">
                        {{ personFor(item.personId)?.handle }}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell v-if="activeTab === 'all'">
                  <Badge variant="secondary" class="gap-1 text-[11px] font-normal">
                    <component :is="icons[item.platform]" class="h-3 w-3" />
                    {{ getPlatformLabel(item.platform) }}
                  </Badge>
                </TableCell>
                <TableCell class="hidden md:table-cell max-w-[24rem]">
                  <span class="text-sm text-muted-foreground line-clamp-1">
                    {{ item.incomingMessage }}
                  </span>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" class="text-[11px] font-normal">
                    {{ item.suggestedAction }}
                  </Badge>
                </TableCell>
                <TableCell class="text-right">
                  <div class="flex items-center justify-end gap-2">
                    <span class="text-xs text-muted-foreground whitespace-nowrap">
                      {{ formatTime(item.timestamp) }}
                    </span>
                    <ChevronDown
                      class="h-4 w-4 text-muted-foreground transition-transform"
                      :class="expandedId === item.id ? 'rotate-180' : ''"
                    />
                  </div>
                </TableCell>
              </TableRow>

              <!-- Expanded review panel -->
              <TableRow v-if="expandedId === item.id" class="hover:bg-transparent bg-muted/20">
                <TableCell :colspan="colspan" class="px-4 py-5 sm:px-6">
                  <div class="max-w-3xl space-y-4">
                    <div class="rounded-lg bg-background border border-border px-3 py-2">
                      <p
                        class="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1"
                      >
                        Incoming message
                      </p>
                      <p class="text-sm text-foreground">{{ item.incomingMessage }}</p>
                    </div>

                    <div class="space-y-2">
                      <p
                        class="text-[10px] font-medium uppercase tracking-wider text-muted-foreground"
                      >
                        Drafted reply
                      </p>
                      <Textarea
                        :model-value="item.draftReply"
                        rows="3"
                        @update:model-value="triage.editDraft(item.id, $event as string)"
                      />
                    </div>

                    <!-- Reasoning trace -->
                    <div class="rounded-lg border-l-2 border-primary/40 bg-muted/40 px-3 py-2.5">
                      <p
                        class="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1"
                      >
                        <Sparkles class="h-3 w-3" />
                        Reasoning
                      </p>
                      <p class="text-xs text-muted-foreground leading-relaxed">
                        {{ item.reasoning }}
                      </p>
                    </div>

                    <div class="flex items-center justify-between pt-1">
                      <button
                        type="button"
                        class="text-xs text-muted-foreground hover:text-foreground transition-colors"
                        @click="router.push(`/relationships/${item.personId}`)"
                      >
                        View profile
                      </button>
                      <div class="flex items-center gap-2">
                        <Button variant="ghost" size="sm" @click="onDismiss(item.id)">
                          <X class="h-4 w-4 mr-1.5" />
                          Dismiss
                        </Button>
                        <Button size="sm" @click="onSend(item.id)">
                          <Send class="h-4 w-4 mr-1.5" />
                          Send
                        </Button>
                      </div>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            </template>

            <TableRow v-if="controls.total.value === 0" class="hover:bg-transparent">
              <TableCell :colspan="colspan" class="h-32 text-center">
                <Search class="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p class="text-sm text-muted-foreground">No messages match your search.</p>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <TablePagination
        :page="controls.page.value"
        :total-pages="controls.totalPages.value"
        :page-size="controls.pageSize.value"
        :range-start="controls.rangeStart.value"
        :range-end="controls.rangeEnd.value"
        :total="controls.total.value"
        noun="messages"
        @update:page="controls.setPage"
        @update:page-size="controls.pageSize.value = $event"
      />
    </template>
  </div>
</template>
