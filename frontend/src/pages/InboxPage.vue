<script setup lang="ts">
import { ref, computed } from 'vue'
import { Inbox, X, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useInboxStore, type InboxItem } from '@/stores/inbox'
import {
  getInboxSourceColor as getSourceColor,
  getInboxSourceIcon as getSourceIcon,
} from '@/lib/inboxFormatters'
import { formatTimestamp } from '@/lib/formatters'
import { markdownToHtml } from '@/lib/markdown'

const inboxStore = useInboxStore()

const selectedItem = ref<InboxItem | null>(null)
const dialogOpen = ref(false)
const activeTab = ref('all')

const activeItems = computed(() => {
  const nonDismissed = inboxStore.activeItems

  let filtered = nonDismissed
  if (activeTab.value === 'read') {
    filtered = nonDismissed.filter((item) => item.read)
  } else if (activeTab.value === 'unread') {
    filtered = nonDismissed.filter((item) => !item.read)
  }

  return filtered
})

const openItemDialog = (item: InboxItem) => {
  selectedItem.value = item
  dialogOpen.value = true
  if (!item.read) {
    inboxStore.markAsRead(item.id)
  }
}

const dismissItem = (item: InboxItem) => {
  inboxStore.dismissItem(item.id)
  if (selectedItem.value?.id === item.id) {
    dialogOpen.value = false
  }
}

const handlePositiveAction = (item: InboxItem) => {
  if (item.actions?.positive?.handler) {
    item.actions.positive.handler()
  }
  dismissItem(item)
}

const handleNegativeAction = (item: InboxItem) => {
  if (item.actions?.negative?.handler) {
    item.actions.negative.handler()
  }
  dismissItem(item)
}

const selectedItemMarkdown = computed(() =>
  selectedItem.value?.longDescription
    ? markdownToHtml(selectedItem.value.longDescription)
    : '',
)
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Inbox class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Your Inbox</h1>
        <Badge
          v-if="inboxStore.unreadCount > 0"
          variant="secondary"
          class="bg-primary/10 text-primary border-primary/20 px-2.5 py-1 rounded-md"
        >
          {{ inboxStore.unreadCount }} new
        </Badge>
      </div>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Your inbox collects system alerts and requests related to your resources and APIs. Review
        items here to approve access, resolve issues, and keep things running smoothly.
      </p>
    </div>

    <!-- Tabs -->
    <Tabs v-model="activeTab" class="w-full mb-8">
      <TabsList
        class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]"
      >
        <TabsTrigger value="all">All</TabsTrigger>
        <TabsTrigger value="unread">Unread</TabsTrigger>
        <TabsTrigger value="read">Read</TabsTrigger>
      </TabsList>
    </Tabs>

    <!-- Empty State -->
    <div v-if="activeItems.length === 0" class="text-center py-12">
      <div class="mx-auto w-14 h-14 bg-muted rounded-full flex items-center justify-center mb-6">
        <Inbox class="h-7 w-7 text-muted-foreground" />
      </div>
      <h3 class="heading-3 mb-3">No items</h3>
      <p class="body-sm text-muted-foreground">Your inbox is empty.</p>
    </div>

    <!-- Inbox Items -->
    <div v-else class="space-y-5">
      <Card
        v-for="item in activeItems"
        :key="item.id"
        class="cursor-pointer hover:shadow-lg transition-all border border-border rounded-xl"
        :class="{
          'border-primary/20 bg-primary/10': !item.read,
        }"
        @click="openItemDialog(item)"
      >
        <CardHeader class="pb-3">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3 flex-1">
              <div :class="`p-2 rounded-lg ${getSourceColor(item.source)}`">
                <component :is="getSourceIcon(item.source)" class="h-4 w-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <Badge variant="outline" class="body-sm">{{ item.source }}</Badge>
                  <span class="body-sm text-muted-foreground">
                    {{ item.timestamp.toLocaleString() }}
                  </span>
                  <div
                    v-if="!item.read"
                    class="w-2 h-2 bg-primary rounded-full animate-pulse"
                  ></div>
                </div>
                <CardTitle class="body-base">{{ item.title }}</CardTitle>
                <CardDescription class="mt-1">{{ item.summary }}</CardDescription>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <!-- Action Buttons -->
              <div v-if="item.actions" class="flex items-center gap-2">
                <Button
                  v-if="item.actions.positive"
                  size="sm"
                  variant="outline"
                  @click.stop="handlePositiveAction(item)"
                >
                  {{ item.actions.positive.label }}
                </Button>
                <Button
                  v-if="item.actions.negative"
                  size="sm"
                  variant="outline"
                  class="text-destructive hover:text-destructive"
                  @click.stop="handleNegativeAction(item)"
                >
                  {{ item.actions.negative.label }}
                </Button>
              </div>
              <!-- Dismiss Button -->
              <Button variant="ghost" size="sm" @click.stop="dismissItem(item)">
                <X class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>
    </div>

    <!-- Item Detail Dialog -->
    <Dialog v-model:open="dialogOpen">
      <DialogContent
        v-if="selectedItem"
        class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl"
      >
        <!-- Header with background -->
        <div class="flex-shrink-0 border-b bg-muted/50">
          <DialogHeader class="p-6 pb-4">
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-3">
                <div :class="`p-3 rounded-lg ${getSourceColor(selectedItem.source)}`">
                  <component :is="getSourceIcon(selectedItem.source)" class="h-5 w-5" />
                </div>
                <div>
                  <div class="flex items-center gap-2 mb-1">
                    <Badge variant="outline" class="body-sm">{{ selectedItem.source }}</Badge>
                    <div
                      v-if="!selectedItem.read"
                      class="flex items-center gap-1 body-sm text-primary"
                    >
                      <div class="w-2 h-2 bg-primary rounded-full"></div>
                      <span>New</span>
                    </div>
                  </div>
                  <span class="body-sm text-muted-foreground">
                    {{ formatTimestamp(selectedItem.timestamp) }}
                  </span>
                </div>
              </div>
            </div>
            <DialogTitle class="heading-3">{{ selectedItem.title }}</DialogTitle>
            <DialogDescription class="mt-2 body-base">{{ selectedItem.summary }}</DialogDescription>
          </DialogHeader>
        </div>

        <!-- Content -->
        <div class="flex-1 min-h-0 overflow-y-auto">
          <div class="p-6">
            <div
              class="prose prose-sm max-w-none prose-headings:font-semibold prose-h2:text-lg prose-h3:text-base prose-p:text-muted-foreground prose-strong:text-foreground prose-code:text-primary prose-code:font-mono prose-pre:bg-muted prose-pre:border prose-pre:font-mono prose-li:text-muted-foreground dark:prose-invert"
              v-html="selectedItemMarkdown"
            />
          </div>
        </div>

        <!-- Footer with actions -->
        <div class="flex-shrink-0 border-t bg-muted/50">
          <DialogFooter class="p-6 pt-4">
            <div class="flex items-center justify-between w-full">
              <div class="flex items-center gap-4">
                <Button
                  variant="ghost"
                  size="default"
                  class="text-muted-foreground hover:text-foreground"
                  @click="
                    () => {
                      selectedItem && dismissItem(selectedItem)
                      dialogOpen = false
                    }
                  "
                >
                  <Trash2 class="h-4 w-4 mr-2" />
                  Dismiss
                </Button>
              </div>
              <div class="flex items-center gap-3">
                <Button
                  v-if="selectedItem.actions?.negative"
                  variant="outline"
                  size="default"
                  @click="selectedItem && handleNegativeAction(selectedItem)"
                >
                  {{ selectedItem.actions.negative.label }}
                </Button>
                <Button
                  v-if="selectedItem.actions?.positive"
                  variant="default"
                  size="default"
                  @click="selectedItem && handlePositiveAction(selectedItem)"
                >
                  {{ selectedItem.actions.positive.label }}
                </Button>
              </div>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

