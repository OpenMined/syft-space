<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[440px]">
      <DialogHeader>
        <DialogTitle>Verify your email</DialogTitle>
        <DialogDescription>
          Enter the 6-digit code we sent to
          <span class="font-medium text-foreground">{{ email }}</span
          >.
        </DialogDescription>
      </DialogHeader>

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div class="space-y-2">
          <Label for="otp-code">Verification code</Label>
          <Input
            id="otp-code"
            v-model="code"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
            placeholder="123456"
            :class="{ 'border-red-500': !!error }"
            @input="onCodeInput"
          />
          <p class="body-sm text-muted-foreground">
            The code expires after 10 minutes. Didn't get one?
            <button
              type="button"
              class="text-primary hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="resending || verifying"
              @click="handleResend"
            >
              {{ resending ? 'Sending…' : 'Resend code' }}
            </button>
          </p>
          <p v-if="resendNotice" class="body-sm text-green-600">{{ resendNotice }}</p>
        </div>

        <Alert v-if="error" variant="destructive">
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <DialogFooter class="gap-2">
          <Button type="button" variant="outline" :disabled="verifying" @click="handleCancel">
            Cancel
          </Button>
          <Button type="submit" :disabled="!isValid || verifying">
            <Loader2 v-if="verifying" class="mr-2 h-4 w-4 animate-spin" />
            Verify
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface Props {
  open: boolean
  email: string
  verifying?: boolean
  resending?: boolean
  error?: string
  // Set when SyftHub didn't emit a code on its own (e.g. an existing
  // unverified account hitting login); the dialog will request one on open.
  autoResend?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  verifying: false,
  resending: false,
  error: '',
  autoResend: false,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  verify: [code: string]
  resend: []
  cancel: []
}>()

const code = ref('')
const resendNotice = ref('')

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const isValid = computed(() => /^\d{6}$/.test(code.value))

const onCodeInput = () => {
  code.value = code.value.replace(/\D+/g, '').slice(0, 6)
}

const handleSubmit = () => {
  if (!isValid.value || props.verifying) return
  emit('verify', code.value)
}

const handleResend = () => {
  resendNotice.value = ''
  emit('resend')
}

const handleCancel = () => {
  emit('cancel')
  emit('update:open', false)
}

let resendAttempted = false

watch(
  () => props.open,
  async (value) => {
    if (!value) return
    code.value = ''
    resendNotice.value = ''
    resendAttempted = false
    await nextTick()
    document.getElementById('otp-code')?.focus()
    if (props.autoResend) emit('resend')
  },
)

// Resend success has no direct signal — infer it from `resending` flipping
// back to false without an error after the user (or auto-resend) triggered one.
watch(
  () => props.resending,
  (now, prev) => {
    if (now) {
      resendAttempted = true
      return
    }
    if (prev && resendAttempted && !props.error) {
      resendNotice.value = 'A fresh code has been sent.'
    }
  },
)
</script>
