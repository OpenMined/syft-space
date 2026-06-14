<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Globe, Slack, Phone } from 'lucide-vue-next'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import PersonModePill from '@/components/PersonModePill.vue'
import {
  getPeopleByPlatform,
  resolveApiForPerson,
  effectiveMode,
} from '@/stores/mockRelationships'
import {
  mockApis,
  PLATFORMS,
  getPlatformDefaultApiId,
  setPlatformDefault,
  type Platform,
} from '@/stores/mockApis'

const router = useRouter()

const icons: Record<Platform, typeof Globe> = {
  syfthub: Globe,
  slack: Slack,
  whatsapp: Phone,
}

const groups = computed(() =>
  PLATFORMS.map((p) => ({
    platform: p.id,
    label: p.label,
    people: getPeopleByPlatform(p.id),
  })),
)

const defaultValue = (platform: Platform) => getPlatformDefaultApiId(platform) ?? 'none'

const onDefaultChange = (platform: Platform, value: string) =>
  setPlatformDefault(platform, value === 'none' ? null : value)

const lastSnippet = (textList: { text: string }[]) =>
  textList.length ? (textList[textList.length - 1]?.text ?? '') : ''
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <!-- Header -->
    <div class="mb-12">
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Relationships</h1>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        The people on the other side of your APIs. Set a default API per platform, or tune how you
        reply to each person.
      </p>
    </div>

    <div class="space-y-10">
      <section v-for="group in groups" :key="group.platform">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-2.5">
            <component :is="icons[group.platform]" class="h-5 w-5 text-muted-foreground" />
            <h2 class="heading-4 text-foreground">{{ group.label }}</h2>
            <span class="text-sm text-muted-foreground">({{ group.people.length }})</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-muted-foreground">Default API</span>
            <Select
              :model-value="defaultValue(group.platform)"
              @update:model-value="onDefaultChange(group.platform, $event as string)"
            >
              <SelectTrigger class="w-56 h-8 text-xs">
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                <SelectItem v-for="api in mockApis" :key="api.id" :value="api.id">
                  {{ api.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div v-if="group.people.length === 0" class="text-sm text-muted-foreground py-3">
          No people on this platform yet.
        </div>

        <div v-else class="space-y-2">
          <div
            v-for="person in group.people"
            :key="person.id"
            class="group flex items-center gap-4 rounded-lg border border-border/50 bg-card p-4 hover:shadow-sm transition-all cursor-pointer"
            @click="router.push(`/relationships/${person.id}`)"
          >
            <Avatar class="h-10 w-10 shrink-0">
              <AvatarFallback class="bg-muted text-muted-foreground text-xs">
                {{ person.avatarInitials }}
              </AvatarFallback>
            </Avatar>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-medium text-foreground truncate">{{ person.name }}</span>
                <span class="text-xs text-muted-foreground truncate">{{ person.handle }}</span>
              </div>
              <p class="text-sm text-muted-foreground truncate">
                {{ lastSnippet(person.conversation) }}
              </p>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <span class="text-xs text-muted-foreground hidden sm:inline">
                {{ resolveApiForPerson(person)?.name ?? 'No API' }}
              </span>
              <PersonModePill :mode="effectiveMode(person)" />
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
