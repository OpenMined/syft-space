<script setup lang="ts">
import { computed } from 'vue'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Globe, Slack, Phone } from 'lucide-vue-next'
import { PLATFORMS, type ChannelBinding, type Platform } from '@/stores/mockApis'

const props = defineProps<{ channels: ChannelBinding[] }>()
const emit = defineEmits<{ 'set-default': [platform: Platform, value: boolean] }>()

const icons: Record<Platform, typeof Globe> = {
  syfthub: Globe,
  slack: Slack,
  whatsapp: Phone,
}

const binding = (platform: Platform): ChannelBinding | undefined =>
  props.channels.find((c) => c.platform === platform)

// SyftHub has no "default auto-reply" concept (it's a marketplace, not a 1:1 channel).
const supportsDefault = (platform: Platform) => platform !== 'syfthub'

const label = (platform: Platform) =>
  PLATFORMS.find((p) => p.id === platform)?.label ?? platform

const platformList = computed(() => PLATFORMS.map((p) => p.id))
</script>

<template>
  <div class="space-y-3">
    <div
      v-for="platform in platformList"
      :key="platform"
      class="rounded-lg border border-border/60 p-3"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <component :is="icons[platform]" class="h-4 w-4 text-muted-foreground" />
          <span class="text-sm font-medium">{{ label(platform) }}</span>
        </div>
        <Switch
          v-if="binding(platform)"
          :model-value="binding(platform)!.enabled"
          @update:model-value="binding(platform)!.enabled = $event"
        />
      </div>

      <div
        v-if="binding(platform)?.enabled && supportsDefault(platform)"
        class="mt-3 flex items-center justify-between pl-6"
      >
        <Label class="text-xs text-muted-foreground">Set as default auto-reply</Label>
        <Switch
          :model-value="binding(platform)!.isDefaultReply"
          @update:model-value="emit('set-default', platform, $event)"
        />
      </div>
    </div>
  </div>
</template>
