<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import ChannelSelector from '@/components/ChannelSelector.vue'
import { UserCheck } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import {
  mockApis,
  generateApiId,
  setPlatformDefault,
  PLATFORMS,
  type ApiResource,
  type ChannelBinding,
  type Platform,
} from '@/stores/mockApis'
import { getAgentById } from '@/stores/mockAgents'

const props = defineProps<{ open: boolean; agentId: string }>()
const emit = defineEmits<{ 'update:open': [value: boolean]; 'api-created': [] }>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const agent = computed(() => getAgentById(props.agentId))

const freshChannels = (): ChannelBinding[] =>
  PLATFORMS.map((p) => ({ platform: p.id, enabled: false, isDefaultReply: false }))

const formData = ref({
  name: '',
  prompt: '',
  hasHilPolicy: true,
  channels: freshChannels(),
})

const isFormValid = computed(() => formData.value.name.trim() !== '')

const resetForm = () => {
  formData.value = {
    name: agent.value ? `${agent.value.name} API` : '',
    prompt: '',
    hasHilPolicy: true,
    channels: freshChannels(),
  }
}

const handleSetDefault = (platform: Platform, value: boolean) => {
  const binding = formData.value.channels.find((c) => c.platform === platform)
  if (binding) binding.isDefaultReply = value
}

const handleCancel = () => {
  isOpen.value = false
}

const handleCreate = () => {
  if (!isFormValid.value || !agent.value) return
  const id = generateApiId()
  const api: ApiResource = {
    id,
    name: formData.value.name.trim(),
    rootType: 'agent',
    rootResourceId: agent.value.id,
    prompt: formData.value.prompt.trim() || null,
    hasHilPolicy: formData.value.hasHilPolicy,
    channels: formData.value.channels.map((c) => ({ ...c })),
  }
  mockApis.push(api)
  agent.value.endpointCount += 1

  // Apply any platform defaults chosen in the channel selector (enforces single default).
  api.channels.forEach((c) => {
    if (c.isDefaultReply) setPlatformDefault(c.platform, id)
  })

  toast.success(`"${api.name}" created`)
  emit('api-created')
  isOpen.value = false
}

watch(isOpen, (open) => {
  if (open) resetForm()
})
</script>

<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="heading-3">Create API</DialogTitle>
        <DialogDescription>
          Expose <span class="font-medium text-foreground">{{ agent?.name }}</span> as a governed
          API and choose where it is reachable.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-6 mt-6">
        <!-- Name -->
        <div class="space-y-2">
          <Label for="api-name" class="text-sm font-medium">
            Name <span class="text-red-500">*</span>
          </Label>
          <Input id="api-name" v-model="formData.name" placeholder="e.g., Personal Assistant API" />
        </div>

        <!-- Base prompt -->
        <div class="space-y-2">
          <Label for="api-prompt" class="text-sm font-medium">Base prompt</Label>
          <Textarea
            id="api-prompt"
            v-model="formData.prompt"
            placeholder="Instructions that shape how this API replies…"
            rows="3"
          />
        </div>

        <!-- HIL policy -->
        <div class="flex items-start justify-between rounded-lg border border-border/60 p-4">
          <div class="flex items-start gap-3">
            <UserCheck class="h-4 w-4 mt-0.5 text-muted-foreground" />
            <div>
              <p class="text-sm font-medium">Require human approval by default</p>
              <p class="text-xs text-muted-foreground">
                Replies are held in Triage for your review before sending.
              </p>
            </div>
          </div>
          <Switch
            :model-value="formData.hasHilPolicy"
            @update:model-value="formData.hasHilPolicy = $event"
          />
        </div>

        <!-- Channels -->
        <div class="space-y-2">
          <Label class="text-sm font-medium">Channels</Label>
          <ChannelSelector :channels="formData.channels" @set-default="handleSetDefault" />
        </div>
      </div>

      <DialogFooter class="mt-8">
        <Button variant="outline" @click="handleCancel">Cancel</Button>
        <Button :disabled="!isFormValid" @click="handleCreate">Create API</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
