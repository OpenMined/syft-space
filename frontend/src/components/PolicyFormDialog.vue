<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle
          >{{ isEditing ? 'Edit' : 'Add' }} {{ getPolicyTypeLabel(policyType) }} Rule</DialogTitle
        >
        <DialogDescription>
          {{ isEditing ? 'Update this' : 'Create a new' }}
          {{
            policyType === 'access'
              ? 'authorization'
              : policyType === 'rate_limit'
                ? 'rate limiting'
                : 'pricing'
          }}
          policy for this endpoint.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Authorization Policy Form -->
        <div v-if="policyType === 'access'" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Rule Type</Label>
              <Select v-model="authorizationForm.ruleType">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue placeholder="Select rule type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="allow" class="body-sm">Allow specific users</SelectItem>
                  <SelectItem value="deny" class="body-sm">Deny specific users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
              <Input
                v-model="authorizationForm.note"
                placeholder="Optional description"
                class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
              />
            </div>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Users</Label>
            <Input
              v-model="authorizationForm.users"
              placeholder="user1@example.com, user2@example.com"
              class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
            />
            <p class="text-xs text-muted-foreground">
              Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
              *@contractors.org)
            </p>
          </div>
        </div>

        <!-- Rate Limiter Policy Form -->
        <div v-if="policyType === 'rate_limit'" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Limit</Label>
              <div class="flex">
                <Input
                  v-model="rateLimiterForm.limit"
                  type="number"
                  placeholder="100"
                  class="h-9 w-20 sm:w-24 rounded-l-lg rounded-r-none border-r-0 border-border bg-card body-sm"
                />
                <Select v-model="rateLimiterForm.windowUnit">
                  <SelectTrigger
                    class="h-9 rounded-r-lg rounded-l-none border-border bg-card body-sm min-w-0"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="second">requests per second</SelectItem>
                    <SelectItem value="minute">requests per minute</SelectItem>
                    <SelectItem value="hour">requests per hour</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Scope</Label>
              <Select v-model="rateLimiterForm.scope">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="per user">For Each User</SelectItem>
                  <SelectItem value="global">For This Endpoint</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
            <Input
              v-model="rateLimiterForm.note"
              placeholder="Optional description"
              class="h-9 rounded-lg border-border bg-card body-sm"
            />
          </div>
        </div>

        <!-- Pricing Policy Form -->
        <div v-if="policyType === 'pricing'" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Price per query ($)</Label>
              <Input
                v-model="pricingForm.price"
                type="number"
                step="any"
                placeholder="Enter price per query"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
              <Input
                v-model="pricingForm.note"
                placeholder="Optional description"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
            </div>
          </div>
          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <div class="space-y-1 sm:flex-shrink-0 sm:w-32">
              <Label class="body-sm text-muted-foreground font-medium">Apply To</Label>
              <Select v-model="pricingForm.userType">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Users</SelectItem>
                  <SelectItem value="specific">Specific Users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div v-if="pricingForm.userType === 'specific'" class="space-y-1 flex-1">
              <Label class="body-sm text-muted-foreground font-medium">Users</Label>
              <Input
                v-model="pricingForm.users"
                placeholder="user1@example.com, user2@example.com"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
              <p class="text-xs text-muted-foreground">
                Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                *@contractors.org)
              </p>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="$emit('update:open', false)" :disabled="isSubmitting"
          >Cancel</Button
        >
        <Button @click="handleSave" :disabled="isSubmitting || !isFormValid">
          <div v-if="isSubmitting" class="flex items-center gap-2">
            <Loader2 class="h-4 w-4 animate-spin" />
            {{ isEditing ? 'Updating...' : 'Creating...' }}
          </div>
          <span v-else>{{ isEditing ? 'Update Rule' : 'Add Rule' }}</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePolicyCreation } from '@/composables/usePolicyCreation'
import { getPolicyTypeLabel } from '@/config/policyTypes'
import type { PolicyTypeId } from '@/config/policyTypes'
import type {
  AuthorizationFormData,
  RateLimitFormData,
  PricingFormData,
} from '@/composables/usePolicyCreation'

const props = defineProps<{
  open: boolean
  policyType: PolicyTypeId
  initialData?: Record<string, unknown> | null
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: [payload: { policyType: PolicyTypeId; formData: Record<string, unknown> }]
}>()

const { validatePolicyForm } = usePolicyCreation()

const isEditing = computed(() => !!props.initialData)

// Local form state
const authorizationForm = ref<AuthorizationFormData>({
  ruleType: 'allow',
  users: '',
  note: '',
})

const rateLimiterForm = ref<RateLimitFormData>({
  limit: '',
  windowUnit: 'minute',
  scope: 'per user',
  note: '',
})

const pricingForm = ref<PricingFormData>({
  price: '',
  userType: 'all',
  users: '',
  note: '',
})

// Get current form data based on policy type
const getCurrentFormData = () => {
  switch (props.policyType) {
    case 'access':
      return authorizationForm.value
    case 'rate_limit':
      return rateLimiterForm.value
    case 'pricing':
      return pricingForm.value
    default:
      return null
  }
}

// Validation
const isFormValid = computed(() => {
  const formData = getCurrentFormData()
  return formData ? validatePolicyForm(props.policyType, formData) : false
})

// Reset form to defaults
const resetForm = (policyType: PolicyTypeId) => {
  switch (policyType) {
    case 'access':
      authorizationForm.value = { ruleType: 'allow', users: '', note: '' }
      break
    case 'rate_limit':
      rateLimiterForm.value = { limit: '', windowUnit: 'minute', scope: 'per user', note: '' }
      break
    case 'pricing':
      pricingForm.value = { price: '', userType: 'all', users: '', note: '' }
      break
  }
}

// Load initial data into form
const loadInitialData = (policyType: PolicyTypeId, data: Record<string, unknown>) => {
  switch (policyType) {
    case 'access':
      authorizationForm.value = {
        ruleType: (data.ruleType as 'allow' | 'deny') || 'allow',
        users: (data.users as string) || '',
        note: (data.note as string) || '',
      }
      break
    case 'rate_limit':
      rateLimiterForm.value = {
        limit: (data.limit as string) || '',
        windowUnit: (data.windowUnit as 'second' | 'minute' | 'hour') || 'minute',
        scope: (data.scope as 'per user' | 'global') || 'per user',
        note: (data.note as string) || '',
      }
      break
    case 'pricing':
      pricingForm.value = {
        price: data.price !== undefined ? String(data.price) : '',
        userType: (data.userType as 'all' | 'specific') || 'all',
        users: (data.users as string) || '',
        note: (data.note as string) || '',
      }
      break
  }
}

// Initialize form when dialog opens
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (props.initialData) {
        loadInitialData(props.policyType, props.initialData)
      } else {
        resetForm(props.policyType)
      }
    }
  },
)

const handleSave = () => {
  const formData = getCurrentFormData()
  if (!formData) return

  emit('save', {
    policyType: props.policyType,
    formData: { ...formData },
  })
}
</script>
