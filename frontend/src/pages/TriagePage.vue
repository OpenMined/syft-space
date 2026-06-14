<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Inbox, Globe, Slack, Phone, Send, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useTriageStore } from '@/stores/triage'
import { getPersonById } from '@/stores/mockRelationships'
import { getPlatformLabel, type Platform } from '@/stores/mockApis'
import { toast } from 'vue-sonner'

const router = useRouter()
const triage = useTriageStore()

const icons: Record<Platform, typeof Globe> = {
  syfthub: Globe,
  slack: Slack,
  whatsapp: Phone,
}

const personFor = (personId: string) => getPersonById(personId)

const onSend = (id: string) => {
  triage.sendTriage(id)
  toast.success('Reply sent')
}
const onDismiss = (id: string) => {
  triage.dismissTriage(id)
  toast.success('Dismissed')
}
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Header -->
    <div class="mb-12">
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Triage</h1>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Drafted replies awaiting your approval — only for people in manual mode. Edit, send, or
        dismiss.
      </p>
    </div>

    <!-- Empty -->
    <div v-if="triage.pendingTriage.length === 0" class="text-center py-16">
      <Inbox class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">Inbox zero</h3>
      <p class="body-sm text-muted-foreground">No replies are waiting for approval.</p>
    </div>

    <!-- Queue -->
    <div v-else class="space-y-4">
      <div
        v-for="item in triage.pendingTriage"
        :key="item.id"
        class="bg-card border border-border rounded-xl p-5"
      >
        <div class="flex items-center justify-between mb-4">
          <button
            class="flex items-center gap-3 hover:opacity-80 transition-opacity"
            @click="router.push(`/relationships/${item.personId}`)"
          >
            <Avatar class="h-9 w-9">
              <AvatarFallback class="bg-muted text-muted-foreground text-xs">
                {{ personFor(item.personId)?.avatarInitials }}
              </AvatarFallback>
            </Avatar>
            <div class="text-left">
              <p class="text-sm font-medium text-foreground">
                {{ personFor(item.personId)?.name }}
              </p>
              <p class="text-xs text-muted-foreground inline-flex items-center gap-1">
                <component :is="icons[item.platform]" class="h-3 w-3" />
                {{ getPlatformLabel(item.platform) }}
              </p>
            </div>
          </button>
          <Badge variant="secondary" class="text-[11px]">{{ item.suggestedAction }}</Badge>
        </div>

        <div class="rounded-lg bg-muted/50 px-3 py-2 mb-4">
          <p class="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
            Incoming
          </p>
          <p class="text-sm text-foreground">{{ item.incomingMessage }}</p>
        </div>

        <div class="space-y-2 mb-3">
          <p class="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Drafted reply
          </p>
          <Textarea
            :model-value="item.draftReply"
            rows="3"
            @update:model-value="triage.editDraft(item.id, $event as string)"
          />
        </div>

        <p class="text-xs text-muted-foreground mb-4">{{ item.rationale }}</p>

        <div class="flex items-center justify-end gap-2">
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
  </div>
</template>
