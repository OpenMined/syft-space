<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Users, ChevronRight } from 'lucide-vue-next'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import PersonModePill from '@/components/PersonModePill.vue'
import {
  getPersonById,
  resolveApiForPerson,
  effectiveMode,
} from '@/stores/mockRelationships'
import { mockApis, getApiById, getPlatformDefaultApiId } from '@/stores/mockApis'

const route = useRoute()
const person = computed(() => getPersonById(route.params.id as string))

const resolvedApi = computed(() => (person.value ? resolveApiForPerson(person.value) : undefined))
const mode = computed(() => (person.value ? effectiveMode(person.value) : 'auto'))

const platformDefaultName = computed(() => {
  if (!person.value) return ''
  const api = getApiById(getPlatformDefaultApiId(person.value.platform))
  return api?.name ?? 'None'
})

// Reply-API select: 'default' sentinel maps to no override.
const apiSelectValue = computed({
  get: () => person.value?.reply.apiOverrideId ?? 'default',
  set: (value: string) => {
    if (person.value) person.value.reply.apiOverrideId = value === 'default' ? null : value
  },
})

const inheritedPrompt = computed(() => resolvedApi.value?.prompt ?? '')

const onPromptInput = (value: string) => {
  if (person.value) person.value.reply.customPrompt = value.trim() ? value : null
}

// The switch sets an explicit pin to the opposite of the current effective mode.
const toggleMode = (checked: boolean) => {
  if (person.value) person.value.reply.modeOverride = checked ? 'auto' : 'manual'
}

const formatTime = (date: Date) =>
  date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Breadcrumb -->
    <div class="flex items-center text-sm text-muted-foreground mb-8">
      <router-link
        to="/relationships"
        class="flex items-center hover:text-foreground transition-colors"
      >
        <Users class="h-4 w-4 mr-2" />
        Relationships
      </router-link>
      <ChevronRight class="h-4 w-4 mx-2" />
      <span class="text-foreground">{{ person?.name }}</span>
    </div>

    <div v-if="!person" class="text-center py-12">
      <p class="text-muted-foreground">Person not found.</p>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-center gap-4 mb-8">
        <Avatar class="h-12 w-12">
          <AvatarFallback class="bg-muted text-muted-foreground">
            {{ person.avatarInitials }}
          </AvatarFallback>
        </Avatar>
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-semibold tracking-tight text-foreground">{{ person.name }}</h1>
            <PersonModePill :mode="mode" />
          </div>
          <p class="text-sm text-muted-foreground">{{ person.handle }}</p>
        </div>
      </div>

      <div class="space-y-6">
        <!-- Metadata -->
        <div class="bg-card border border-border rounded-xl p-6">
          <h3 class="heading-4 mb-3">Notes</h3>
          <Textarea
            v-model="person.metadata"
            rows="3"
            placeholder="What should your assistant know about this person?"
          />
        </div>

        <!-- Reply settings -->
        <div class="bg-card border border-border rounded-xl p-6 space-y-5">
          <h3 class="heading-4">Reply settings</h3>

          <div class="space-y-2">
            <Label class="text-sm font-medium">Reply API</Label>
            <Select v-model="apiSelectValue">
              <SelectTrigger class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">
                  Use platform default ({{ platformDefaultName }})
                </SelectItem>
                <SelectItem v-for="api in mockApis" :key="api.id" :value="api.id">
                  {{ api.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="space-y-2">
            <Label class="text-sm font-medium">Custom prompt</Label>
            <Textarea
              :model-value="person.reply.customPrompt ?? ''"
              rows="2"
              :placeholder="inheritedPrompt || 'Inherits the API prompt'"
              @update:model-value="onPromptInput($event as string)"
            />
          </div>

          <div class="flex items-center justify-between rounded-lg border border-border/60 p-4">
            <div>
              <p class="text-sm font-medium">Reply mode</p>
              <p class="text-xs text-muted-foreground">
                Manual replies are held in Triage for your approval.
              </p>
            </div>
            <div class="flex items-center gap-3">
              <PersonModePill :mode="mode" />
              <Switch :model-value="mode === 'auto'" @update:model-value="toggleMode($event)" />
            </div>
          </div>
        </div>

        <!-- Conversation -->
        <div class="bg-card border border-border rounded-xl p-6">
          <h3 class="heading-4 mb-4">Conversation</h3>
          <ScrollArea class="h-72 pr-4">
            <div class="space-y-3">
              <div
                v-for="message in person.conversation"
                :key="message.id"
                class="flex"
                :class="message.direction === 'out' ? 'justify-end' : 'justify-start'"
              >
                <div
                  class="max-w-[75%] rounded-2xl px-4 py-2"
                  :class="
                    message.direction === 'out'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  "
                >
                  <p class="text-sm whitespace-pre-wrap">{{ message.text }}</p>
                  <p
                    class="text-[10px] mt-1 opacity-70"
                    :class="message.direction === 'out' ? 'text-right' : ''"
                  >
                    {{ formatTime(message.timestamp) }}
                    <span v-if="message.wasDraft"> · approved</span>
                  </p>
                </div>
              </div>
            </div>
          </ScrollArea>
        </div>
      </div>
    </template>
  </div>
</template>
