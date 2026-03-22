<template>
  <div :class="compact ? 'space-y-3' : 'space-y-4'">
    <!-- Loading -->
    <div v-if="isLoading" class="bg-card border border-border rounded-xl p-6">
      <div class="flex items-center gap-3">
        <Loader2 class="h-5 w-5 animate-spin text-muted-foreground" />
        <span class="body-sm text-muted-foreground">Checking wallet status...</span>
      </div>
    </div>

    <!-- No wallet configured -->
    <div
      v-else-if="!wallet && !isConfiguring"
      class="bg-card border border-border rounded-xl p-6"
    >
      <div class="flex flex-col items-center gap-3 text-center">
        <CreditCard class="h-8 w-8 text-muted-foreground" />
        <div>
          <p class="body-sm font-medium">No payment provider configured</p>
          <p class="text-xs text-muted-foreground mt-1">
            Connect your Xendit account to start accepting payments
          </p>
        </div>
        <Button variant="outline" size="sm" @click="isConfiguring = true">
          <CreditCard class="h-4 w-4 mr-2" />
          Configure Xendit
        </Button>
      </div>
    </div>

    <!-- Configuration form -->
    <div
      v-else-if="isConfiguring"
      class="bg-card border border-border rounded-xl p-6 space-y-4"
    >
      <div class="space-y-1">
        <Label class="body-sm text-muted-foreground font-medium">API Key</Label>
        <Input
          v-model="apiKey"
          type="password"
          placeholder="Enter your Xendit API key"
          class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
        />
      </div>
      <div class="space-y-1">
        <Label class="body-sm text-muted-foreground font-medium">Callback Token</Label>
        <Input
          v-model="callbackToken"
          type="password"
          placeholder="Enter your Xendit callback verification token"
          class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
        />
        <p class="text-xs text-muted-foreground">
          Find this in your Xendit Dashboard &rarr; Settings &rarr; Developers &rarr; Webhook
          Verification Token
        </p>
      </div>
      <p v-if="error" class="text-xs text-destructive">{{ error }}</p>
      <div class="flex gap-2">
        <Button size="sm" :disabled="!isFormValid || isSaving" @click="handleConfigure">
          <Loader2 v-if="isSaving" class="h-4 w-4 mr-2 animate-spin" />
          Save
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="isSaving"
          @click="isConfiguring = false"
        >
          Cancel
        </Button>
      </div>
    </div>

    <!-- Wallet connected -->
    <div v-else-if="wallet" class="bg-card border border-border rounded-xl p-6 space-y-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <CreditCard class="h-4 w-4 text-muted-foreground" />
          <span class="body-sm font-medium">Xendit</span>
        </div>
        <Badge variant="outline" class="text-xs">
          <div class="w-2 h-2 bg-green-500 rounded-full mr-1" />
          Connected
        </Badge>
      </div>
      <div class="space-y-1">
        <Label class="text-xs text-muted-foreground">Webhook URL</Label>
        <div class="flex items-center gap-2">
          <code
            class="flex-1 text-xs bg-muted rounded-lg px-3 py-2 truncate text-muted-foreground"
          >
            {{ wallet.webhookUrl }}
          </code>
          <Button
            variant="ghost"
            size="sm"
            class="h-8 w-8 p-0 shrink-0"
            @click="copyWebhookUrl"
          >
            <Check v-if="copied" class="h-3.5 w-3.5 text-green-500" />
            <Copy v-else class="h-3.5 w-3.5" />
          </Button>
        </div>
        <p class="text-xs text-muted-foreground">
          Copy this URL and paste it in your
          <span class="font-medium">Xendit Dashboard &rarr; Settings &rarr; Webhooks</span>
        </p>
      </div>
      <Button variant="destructive" size="sm" :disabled="isDeleting" @click="handleDelete">
        <Loader2 v-if="isDeleting" class="h-4 w-4 mr-2 animate-spin" />
        <Trash2 v-else class="h-4 w-4 mr-2" />
        Delete
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { CreditCard, Check, Copy, Trash2, Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { useWallet } from '@/composables/useWallet'

withDefaults(
  defineProps<{
    compact?: boolean
  }>(),
  { compact: false },
)

const emit = defineEmits<{
  configured: []
}>()

const { wallet, isLoading, fetchWallet, configure, remove } = useWallet()
const isConfiguring = ref(false)
const apiKey = ref('')
const callbackToken = ref('')
const isSaving = ref(false)
const isDeleting = ref(false)
const copied = ref(false)
const error = ref('')

const isFormValid = computed(
  () => apiKey.value.trim() !== '' && callbackToken.value.trim() !== '',
)

const handleConfigure = async () => {
  isSaving.value = true
  error.value = ''
  try {
    await configure(apiKey.value, callbackToken.value)
    isConfiguring.value = false
    emit('configured')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to configure wallet'
  } finally {
    isSaving.value = false
  }
}

const handleDelete = async () => {
  isDeleting.value = true
  try {
    await remove()
    apiKey.value = ''
    callbackToken.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete wallet'
  } finally {
    isDeleting.value = false
  }
}

const copyWebhookUrl = async () => {
  if (!wallet.value?.webhookUrl) return
  try {
    await navigator.clipboard.writeText(wallet.value.webhookUrl)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    error.value = 'Failed to copy to clipboard'
  }
}

onMounted(() => {
  fetchWallet()
})
</script>
